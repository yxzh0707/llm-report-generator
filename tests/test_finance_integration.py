import asyncio
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_runtime_integration import RUNTIME, ToolFake, message
from langchain_core.messages import AIMessage
from runtime_adapter import assemble, agent_input, REPORT_PATH, tool_names
from finance_evidence import FINANCE_TOOLS, bounded_arguments, financial_snapshot, source_identity
from phase1_request_policy import ReportRequest, required_headings
from run_report import DEFAULT_BUDGET

FACTS = {'entity': 'Fixture issuer', 'cik': '1045810', 'concept': 'Assets',
         'facts': [{'unit': 'USD', 'val': 1000000, 'end': '2025-01-26', 'filed': '2025-02-26'}]}
ARGS = {'identifier': '1045810', 'concept': 'Assets'}


def replay(name, args, value):
    return {json.dumps({'name': name, 'arguments': bounded_arguments(name, args)}, sort_keys=True): value}


@unittest.skipUnless(RUNTIME, 'requires runtime environment')
class FinanceTests(unittest.TestCase):
    def test_scope_closure(self):
        self.assertTrue(FINANCE_TOOLS <= tool_names('web_only'))
        self.assertTrue(FINANCE_TOOLS <= tool_names('hybrid'))
        for mode in ('uploaded_only', 'web_only', 'hybrid'):
            self.assertFalse(FINANCE_TOOLS & tool_names(mode, frozen=True))
        self.assertFalse(FINANCE_TOOLS & tool_names('uploaded_only'))

    def test_complete_record_projection_and_query_identity(self):
        value = {**FACTS, 'facts': FACTS['facts'] * 100}
        text, truncated = financial_snapshot('sec_company_facts', ARGS, value)
        self.assertLessEqual(len(text), 6000)
        self.assertTrue(truncated)
        self.assertEqual(json.loads(text)['data']['facts'][0], FACTS['facts'][0])
        a = source_identity('sec_company_facts', ARGS, FACTS)[2]
        b = source_identity('sec_company_facts', {**ARGS, 'before': '2024-01-01'}, FACTS)[2]
        self.assertNotEqual(a, b)
        rows = {'fields': ['date', 'price'], 'items': [['2025-01-01', 12.5]] * 500}
        text, _ = financial_snapshot('tushare_query', {'api_name': 'daily', 'params': {}}, rows)
        data = json.loads(text)['data']
        self.assertEqual(data['fields'], rows['fields'])
        self.assertTrue(all(len(r) == 2 for r in data['items']))
        with self.assertRaises(ValueError):
            bounded_arguments('alpha_vantage', {'function': 'OVERVIEW', 'params': {'apikey': 'private'}})
        for value in ({}, {'Information': 'quota exhausted'}, {'error': 'no key'}, {'Global Quote': {}}):
            with self.assertRaises(ValueError):
                financial_snapshot('alpha_vantage', {}, value)

    def test_native_loop_finance_citation_audit_web_and_hybrid(self):
        async def check():
            for mode in ('web_only', 'hybrid'):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory); out = root/'out'; out.mkdir()
                    corpus = root/'corpus'; corpus.mkdir()
                    (corpus/'a.md').write_text('Fixture issuer total assets were reported in USD.')
                    req = ReportRequest(task='Describe assets', source_mode=mode)
                    refs = '[S1] [S2]' if mode == 'hybrid' else '[S1]'
                    report = '\n\n'.join('## '+h+'\n\nAssets are 1 million USD. '+refs
                                         for h in required_headings(req.structure))
                    responses = ([message('retrieve_uploaded_documents', {}, 'upload')] if mode == 'hybrid' else [])
                    responses += [message('sec_company_facts', ARGS, 'facts'),
                        message('write_file', {'path': REPORT_PATH, 'content': report}, 'save'),
                        AIMessage(content='Report generated.')]
                    runtime, evidence = assemble(out, req, corpus, ['a'], ['assets'], None,
                        DEFAULT_BUDGET, model=ToolFake(responses=responses),
                        web_replay=replay('sec_company_facts', ARGS, FACTS))
                    result = await runtime.arun(agent_input(req)); await runtime.aclose()
                    self.assertEqual(result.status, 'succeeded', result.terminal)
                    api = [s for s in evidence.sources if s.get('access_method') == 'financial_api'][0]
                    self.assertEqual(json.loads(api['text'])['data']['facts'], FACTS['facts'])
                    self.assertTrue((out/api['raw_response_path']).is_file())
                    audit = json.loads((out/'enhanced_evidence_audit.json').read_text())
                    self.assertEqual(audit['linked_sources'], 2 if mode == 'hybrid' else 1)
                    self.assertFalse(audit['claim_support_validated'])
        asyncio.run(check())

    def test_discovery_and_failures_do_not_authorize_report(self):
        async def check():
            cases = [
                ('sec_filings', {'identifier': '1045810'}, {'filings': [
                    {'url': 'https://www.sec.gov/Archives/example.htm', 'form': '10-K'}]}),
                ('sec_company_facts', ARGS, {'error': 'Rate limit'}),
                ('sec_company_facts', ARGS, {**FACTS, 'facts': []}),
                ('alpha_vantage', {'function': 'OVERVIEW', 'params': {'symbol': 'NVDA'}}, {}),
            ]
            for name, args, value in cases:
                with tempfile.TemporaryDirectory() as directory:
                    out = Path(directory); req = ReportRequest(task='test', source_mode='web_only')
                    runtime, evidence = assemble(out, req, None, [], [], None, DEFAULT_BUDGET,
                        model=ToolFake(responses=[message(name, args, 'api'),
                            message('write_file', {'path': REPORT_PATH, 'content': 'Unsupported'}, 'save'),
                            AIMessage(content='Unavailable')]), web_replay=replay(name, args, value))
                    result = await runtime.arun(agent_input(req)); await runtime.aclose()
                    self.assertEqual(evidence.sources, [])
                    self.assertFalse((out/'raw_report.md').exists())
                    self.assertTrue(any(e.data.get('action') == 'source_precondition_denied' for e in result.trajectory))
        asyncio.run(check())

    def test_uploaded_runtime_denies_finance_and_frozen_replay_never_falls_back(self):
        async def check():
            from autoresearch_frontier_finance.runtime_adapter import FFlowMiddleware
            for name in FINANCE_TOOLS:
                with tempfile.TemporaryDirectory() as directory:
                    req = ReportRequest(task='test', source_mode='uploaded_only')
                    runtime, evidence = assemble(Path(directory), req, None, [], [], None,
                        DEFAULT_BUDGET, model=ToolFake(responses=[message(name, {}, 'denied')]))
                    result = await runtime.arun(agent_input(req)); await runtime.aclose()
                    self.assertEqual(result.terminal.error_code, 'tool_not_allowed')
                    self.assertEqual(evidence.tool_log, [])
            with tempfile.TemporaryDirectory() as directory:
                req = ReportRequest(task='test', source_mode='web_only')
                runtime, evidence = assemble(Path(directory), req, None, [], [], None,
                    DEFAULT_BUDGET, model=ToolFake(responses=[AIMessage(content='unused')]), web_replay={})
                with patch.object(FFlowMiddleware, '_call', side_effect=AssertionError('Network forbidden')):
                    value = json.loads(await evidence._call('sec_company_facts', ARGS))
                self.assertIn('error', value)
                self.assertEqual(evidence.sources, [])
                await runtime.aclose()
        asyncio.run(check())

    def test_other_financial_apis_and_environment_aliases(self):
        async def check():
            from types import SimpleNamespace
            cases = [
                ('tushare_query', {'api_name': 'daily', 'params': {'ts_code': '000001.SZ'}},
                 {'fields': ['ts_code', 'trade_date', 'close'], 'items': [['000001.SZ', '20250102', 11.2]]}),
                ('alpha_vantage', {'function': 'OVERVIEW', 'params': {'symbol': 'NVDA'}},
                 {'Symbol': 'NVDA', 'Currency': 'USD', 'LatestQuarter': '2025-01-31', 'TotalAssets': '1000000'}),
            ]
            for name, args, value in cases:
                with tempfile.TemporaryDirectory() as directory:
                    out = Path(directory); req = ReportRequest(task='test', source_mode='web_only')
                    with patch.dict('os.environ', {'TUSHARE_TOKEN': 'fixture-tushare',
                                                  'ALPHA_VANTAGE_API_KEY': 'fixture-alpha'}, clear=True):
                        runtime, evidence = assemble(out, req, None, [], [], None, DEFAULT_BUDGET,
                            model=ToolFake(responses=[AIMessage(content='unused')]),
                            web_replay=replay(name, args, value))
                    result = await evidence._call(name, args)
                    context = SimpleNamespace(metadata={}, record=lambda *a, **k: None)
                    evidence._record_scope(context, name, args, result)
                    self.assertEqual(len(evidence.sources), 1)
                    self.assertEqual(context.metadata['_evidence_ledger'][0]['tool_name'], name)
                    flags = json.loads((out/'financial_capabilities.json').read_text())['credentials_available']
                    self.assertTrue(flags['TUSHARE_API_KEY'])
                    self.assertTrue(flags['ALPHAVANTAGE_API_KEY'])
                    self.assertNotIn('fixture-alpha', ''.join(p.read_text() for p in out.glob('*.json')))
                    await runtime.aclose()
        asyncio.run(check())
