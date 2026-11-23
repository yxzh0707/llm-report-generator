import asyncio
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
try:
    from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
    from langchain_core.messages import AIMessage
    from runtime_adapter import assemble, agent_input, tool_names, OutputStore, REPORT_PATH
    RUNTIME = True
except ImportError:
    RUNTIME = False
from phase1_request_policy import ReportRequest, required_headings
from phase1_document_retrieval import load_documents
from run_report import DEFAULT_BUDGET

if RUNTIME:
    class ToolFake(FakeMessagesListChatModel):
        def bind_tools(self, tools, **kwargs):
            return self


def message(name, args, identity):
    return AIMessage(content='', tool_calls=[{'name': name, 'args': args, 'id': identity, 'type': 'tool_call'}])


@unittest.skipUnless(RUNTIME, 'requires .venv-runtime / Python 3.12')
class RuntimeTests(unittest.TestCase):
    def test_planning_ablation_keeps_explicit_requirement_without_save_gate(self):
        async def check():
            with tempfile.TemporaryDirectory() as directory:
                root=Path(directory);corpus=root/'corpus';corpus.mkdir()
                (corpus/'a.md').write_text('# A\n\nRevenue increased 10 percent.')
                out=root/'out';out.mkdir();req=ReportRequest(task='Summarise revenue',max_words=50)
                report='\n\n'.join('## '+h+'\n\nRevenue increased [S1].' for h in required_headings(req.structure))
                report=report.replace('## Sources','word '*100+'\n\n## Sources')
                fake=ToolFake(responses=[message('retrieve_uploaded_documents',{},'r'),
                    message('write_file',{'path':REPORT_PATH,'content':report},'w'),AIMessage(content='Done')])
                runtime,evidence=assemble(out,req,corpus,['a'],['revenue'],None,DEFAULT_BUDGET,model=fake,length_control='planning_only')
                result=await runtime.arun(agent_input(req,length_control='planning_only'));await runtime.aclose()
                self.assertEqual(result.status,'succeeded')
                self.assertEqual((out/'raw_report.md').read_text(),report)
                self.assertFalse((out/'length_checks.json').exists())
                prompt=(out/'agent/SKILL.md').read_text()
                self.assertIn('allocate a word budget',prompt)
                self.assertNotIn('No numeric word limit',prompt)
                self.assertNotIn('check_report_length',(out/'agent/agent.yaml').read_text())
        asyncio.run(check())

    def test_over_limit_write_returns_feedback_then_accepts_shorter_report(self):
        async def check():
            with tempfile.TemporaryDirectory() as directory:
                root=Path(directory); corpus=root/'corpus';corpus.mkdir()
                (corpus/'a.md').write_text('# A\n\nRevenue increased 10 percent.')
                out=root/'out';out.mkdir()
                req=ReportRequest(task='Summarise revenue',depth='brief',min_words=250,max_words=500)
                prefix='\n\n'.join('## '+h+'\n\nReported revenue [S1].' for h in required_headings(req.structure) if h!='Sources')
                too_long=prefix+'\n\n'+'word '*501+'\n\n## Sources\n\n[S1] A'
                corrected=prefix+'\n\n'+'word '*280+'\n\n## Sources\n\n[S1] A'
                fake=ToolFake(responses=[message('retrieve_uploaded_documents',{},'retrieve'),
                    message('check_report_length',{'content':too_long},'count'),
                    message('write_file',{'path':REPORT_PATH,'content':too_long},'bad'),
                    message('write_file',{'path':REPORT_PATH,'content':corrected},'good'),
                    AIMessage(content='Report generated.')])
                runtime,evidence=assemble(out,req,corpus,['a'],['revenue'],None,DEFAULT_BUDGET,model=fake)
                result=await runtime.arun(agent_input(req));await runtime.aclose()
                self.assertEqual(result.status,'succeeded',result.terminal)
                self.assertEqual((out/'raw_report.md').read_text(),corrected)
                checks=json.loads((out/'length_checks.json').read_text())
                self.assertEqual([c['can_save'] for c in checks],[False,False,True])
                self.assertTrue(any(e.data.get('action')=='report_length_denied' for e in result.trajectory))
                self.assertEqual(checks[0]['body_words'], checks[1]['body_words'])
                self.assertIn('excess_words', checks[1])
                self.assertEqual(checks[0]['body_token_measurement']['count'], 800)
                self.assertIsNotNone(checks[0]['draft_target_tokens_estimate'])
                correction_inputs=[e.data for e in result.trajectory
                    if e.type=='model_input_captured' and e.data.get('model_call')==3]
                self.assertEqual(correction_inputs[0]['request_contract']['tools'],['revise_report_text'])
                self.assertIn('The deterministic body count', correction_inputs[0]['system_message'])
                self.assertIn('tokenizer measured 800 body tokens', correction_inputs[0]['system_message'])
                self.assertEqual(len(evidence.length_revision_events),2)
                # A rewrite uses the current draft and requirements, with no
                # failed draft/tool-history accumulation or hidden model call.
                payloads=[e.data for e in result.trajectory if e.type=='model_input_captured' and e.data.get('model_call')==4]
                serialized=json.dumps(payloads[0])
                self.assertIn('shorten_selected_narrative_blocks',serialized)
                self.assertIn('target_block_words',serialized)
                self.assertIn('report_task',serialized)
        with patch('runtime_adapter.ReportTokenMeter.measure', return_value={
                'count': 800, 'exact_for_text': True, 'method': 'mock_tokenizer'}):
            asyncio.run(check())

    def test_frozen_hybrid_replays_both_classes_with_stable_ids(self):
        from provenance import digest
        async def check():
            with tempfile.TemporaryDirectory() as directory:
                out=Path(directory)
                def source(kind, identity, text):
                    return {'source_kind':kind,'document_id':identity,'title':identity,
                        'source_url':'https://example.org/'+identity,'retrieval_url':kind+'://'+identity,
                        'text':text,'text_sha256':digest(text.encode()),'char_start':0,'char_end':len(text),
                        'chunk_id':identity,'evidence_id':identity}
                packet={'source_mode':'hybrid','uploaded':[source('uploaded','a','Reported revenue 10.')],
                        'web':[source('web','b','Reported revenue 20.')],'retrieval':{'mode':'frozen'}}
                req=ReportRequest(task='compare',source_mode='hybrid')
                report='\n\n'.join('## '+h+'\n\nReported revenue [S1] [S2].' for h in required_headings(req.structure))
                model=ToolFake(responses=[message('retrieve_uploaded_documents',{},'u'),
                    message('retrieve_web_documents',{},'w'),
                    message('write_file',{'path':REPORT_PATH,'content':report},'save'),AIMessage(content='Report generated.')])
                runtime,evidence=assemble(out,req,None,[],[],None,DEFAULT_BUDGET,model=model,frozen_evidence=packet)
                result=await runtime.arun(agent_input(req));await runtime.aclose()
                self.assertEqual(result.status,'succeeded',result.terminal)
                self.assertEqual([(s['citation'],s['source_kind']) for s in evidence.sources],
                                 [('[S1]','uploaded'),('[S2]','web')])
                self.assertEqual(json.loads((out/'enhanced_evidence_audit.json').read_text())['linked_sources'],2)
                self.assertNotIn('web_search', {t.name for t in evidence.tools})
        asyncio.run(check())

    def test_prompt_limit_prevents_provider_attempt(self):
        async def check():
            with tempfile.TemporaryDirectory() as directory:
                out=Path(directory);req=ReportRequest(task='x'*70000,source_mode='web_only')
                runtime,evidence=assemble(out,req,None,[],[],None,DEFAULT_BUDGET,
                    model=ToolFake(responses=[AIMessage(content='unused')]),web_replay={})
                result=await runtime.arun(agent_input(req));await runtime.aclose()
                self.assertEqual(result.status,'failed')
                self.assertFalse((out/'provider_attempts.json').exists())
        asyncio.run(check())

    def test_native_model_timeout_and_bounded_retry(self):
        class FailOnce(ToolFake):
            attempts: int = 0
            async def _agenerate(self, messages, **kwargs):
                self.attempts += 1
                if self.attempts == 1:
                    raise ConnectionError('fixture transient connection')
                return await super()._agenerate(messages, **kwargs)
        class Slow(ToolFake):
            async def _agenerate(self, messages, **kwargs):
                await asyncio.sleep(1)
                return await super()._agenerate(messages, **kwargs)
        async def check():
            for kind in ['retry', 'timeout']:
                with tempfile.TemporaryDirectory() as directory:
                    model = FailOnce(responses=[AIMessage(content='Recovered')]) if kind == 'retry' else Slow(responses=[AIMessage(content='Late')])
                    budget = {**DEFAULT_BUDGET, 'model_retries': int(kind == 'retry'),
                              'model_timeout_seconds': 0.02 if kind == 'timeout' else 2}
                    req = ReportRequest(task='test', source_mode='web_only')
                    runtime, evidence = assemble(Path(directory), req, None, [], [], None, budget,
                                                  model=model, web_replay={})
                    output = await runtime.arun(agent_input(req))
                    await runtime.aclose()
                    if kind == 'retry':
                        self.assertEqual(output.status, 'succeeded', output.terminal)
                        self.assertEqual(model.attempts, 2)
                    else:
                        self.assertEqual(output.status, 'timed_out', output.terminal)
                    self.assertTrue(output.trajectory)
        asyncio.run(check())

    def test_native_tool_timeout_is_recorded_and_not_silently_successful(self):
        from autoresearch_frontier_finance.runtime_adapter import FFlowMiddleware
        async def stalled(*args, **kwargs):
            await asyncio.sleep(1)
            return '{}'
        async def check():
            with tempfile.TemporaryDirectory() as directory:
                req = ReportRequest(task='test', source_mode='web_only')
                fake = ToolFake(responses=[message('web_search', {'query':'test'}, 'search'), AIMessage(content='Source unavailable')])
                runtime, evidence = assemble(Path(directory), req, None, [], [], None,
                    {**DEFAULT_BUDGET, 'tool_timeout_seconds': 0.01}, model=fake)
                with patch.object(FFlowMiddleware, '_call', stalled):
                    output = await runtime.arun(agent_input(req))
                await runtime.aclose()
                self.assertTrue(any(t.status == 'failed' for t in output.tool_calls), output.tool_calls)
                self.assertEqual(evidence.sources, [])
        asyncio.run(check())

    def test_real_loop_document_tool_evidence_gate_and_saved_report(self):
        async def check():
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                corpus = root / 'corpus'; corpus.mkdir()
                (corpus/'a.md').write_text('# A\n\nData center revenue increased 10 percent.')
                (corpus/'b.txt').write_text('# B\n\nData center revenue increased 20 percent.')
                out = root/'out'; out.mkdir()
                req = ReportRequest(task='Compare data center revenue')
                report = '\n\n'.join('## '+h+'\n\nReported revenue [S1] [S2].' for h in required_headings(req.structure))
                fake = ToolFake(responses=[message('retrieve_uploaded_documents', {}, 'retrieve'),
                    message('write_file', {'path': REPORT_PATH, 'content': report}, 'save'),
                    AIMessage(content=report)])
                runtime, evidence = assemble(out, req, corpus, ['a','b'], ['data center revenue'], None,
                                             DEFAULT_BUDGET, model=fake)
                result = await runtime.arun(agent_input(req))
                await runtime.aclose()
                self.assertEqual(result.status, 'succeeded', result.terminal)
                self.assertEqual((out/'raw_report.md').read_text(), report)
                self.assertEqual(len(evidence.sources), 2)
                ledger = json.loads((out/'enhanced_evidence_ledger.json').read_text())
                self.assertEqual({r['source_id'] for r in ledger}, {'[S1]', '[S2]'})
                audit = json.loads((out/'enhanced_evidence_audit.json').read_text())
                self.assertEqual(audit['linked_sources'], 2)
                self.assertFalse(audit['claim_support_validated'])
                actions = {e.data.get('action') for e in result.trajectory}
                self.assertIn('report_gate_report_saved', actions)
                self.assertIn('fflow_scope_updated', actions)
                self.assertNotIn('check_report_length', (out/'agent/agent.yaml').read_text())
                self.assertFalse((out/'length_checks.json').exists())
                self.assertNotIn('allocate a word budget', (out/'agent/SKILL.md').read_text())
        asyncio.run(check())

    def test_mode_matrix_denies_disallowed_tools_at_runtime(self):
        async def check():
            for mode, forbidden in {'uploaded_only': ['web_search', 'web_fetch', 'read_file', 'sandbox_command'],
                                    'web_only': ['retrieve_uploaded_documents', 'read_file', 'sandbox_python'],
                                    'hybrid': ['read_file', 'sandbox_command']}.items():
                for name in forbidden:
                    with tempfile.TemporaryDirectory() as directory:
                        out = Path(directory)
                        runtime, evidence = assemble(out, ReportRequest(task='test', source_mode=mode),
                            out/'DO_NOT_READ', [], None, None, DEFAULT_BUDGET,
                            model=ToolFake(responses=[message(name, {}, 'denied')]), web_replay={})
                        result = await runtime.arun(agent_input(ReportRequest(task='test', source_mode=mode)))
                        await runtime.aclose()
                        self.assertIn(result.status, {'failed', 'invalid_output'})
                        self.assertEqual(result.terminal.error_code, 'tool_not_allowed')
                        self.assertEqual(evidence.tool_log, [])
                        self.assertEqual(evidence.sources, [])
        asyncio.run(check())

    def test_output_store_cannot_read_inputs_or_traverse(self):
        async def check():
            with tempfile.TemporaryDirectory() as directory:
                store = OutputStore(directory)
                for path in ['../secret', '/etc/passwd', 'work/inputs/a.md', 'work/outputs/../inputs/a.md']:
                    with self.assertRaises(PermissionError):
                        await store.read_file(path)
                    with self.assertRaises(PermissionError):
                        await store.write_file(path, 'bad')
        asyncio.run(check())

    def test_web_only_never_opens_corpus_or_upload_cache(self):
        async def check():
            with tempfile.TemporaryDirectory() as directory:
                out = Path(directory)
                req = ReportRequest(task='web task', source_mode='web_only')
                runtime, evidence = assemble(out, req, out/'absent', ['secret'], ['private words'],
                    object(), DEFAULT_BUDGET, model=ToolFake(responses=[AIMessage(content='No evidence.')]), web_replay={})
                self.assertIsNone(evidence.corpus_root)
                self.assertIsNone(evidence.embeddings)
                self.assertEqual(evidence.queries, [])
                await runtime.arun(agent_input(req))
                await runtime.aclose()
        asyncio.run(check())


class IngestionIdentityTests(unittest.TestCase):
    def test_collisions_and_missing_ids_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'a.md').write_text('one')
            with self.assertRaises(ValueError):
                load_documents(root, ['missing'])
            (root/'a.txt').write_text('two')
            with self.assertRaisesRegex(ValueError, 'collision'):
                load_documents(root)

    def test_bytes_and_normalized_hash_are_distinct(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)/'a.txt'; p.write_bytes(b'\r\nHello\r\n\r\n\r\nWorld\r\n')
            d = load_documents(p.parent)[0]
            self.assertEqual(d.text, 'Hello\n\nWorld')
            self.assertNotEqual(d.sha256, d.file_sha256)
