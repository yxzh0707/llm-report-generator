import asyncio
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from calculation_precision import input_precision_policy, normalize
from report_calculations import calculate_metrics
from report_outcome import delivery_outcome
from report_validation import validate_report

TASK = ('Round each to one decimal USD billion from the most precise figure available. '
        'Use the displayed one-decimal quarterly amounts for ALL calculations.')
SOURCES = [{'citation': '[S1]'}, {'citation': '[S2]'}]


def plan():
    facts = [dict(id='Q3', value='9.44', unit='USD billions', period='Q3 FY2025', citations=['[S1]'], report_label='Revenue Q3'),
             dict(id='Q4', value='9993', unit='USD millions', period='Q4 FY2025', citations=['[S2]'], report_label='Revenue Q4')]
    metrics = [dict(id='growth', operation='percent_change', inputs=['Q3','Q4'], decimal_places=1, report_label='Growth')]
    return facts, metrics


class PrecisionRepairTests(unittest.TestCase):
    def test_negative_currency_sign_is_preserved_without_accepting_positive_or_wrong_currency(self):
        from report_validation import result_matches
        node=dict(status='available',value='-93.6',unit='USD billions')
        for value in ['−$93.6 billion','-$93.6 billion','USD -93.6 billion','-93.6 billion']:
            self.assertTrue(result_matches(value,node),value)
        for value in ['$93.6 billion','+93.6 billion','EUR -93.6 billion','-EUR 93.6 billion']:
            self.assertFalse(result_matches(value,node),value)

    def test_mixed_scale_original_values_become_requested_inputs_before_growth(self):
        facts, metrics = plan()
        result = calculate_metrics(facts, metrics, SOURCES, input_policy=input_precision_policy(TASK))
        self.assertEqual([f['value'] for f in result['facts']], ['9.4','10.0'])
        self.assertEqual(result['facts'][1]['original_value'], '9993')
        self.assertEqual(result['metrics'][0]['value'], '6.4')
        self.assertEqual(facts[1]['value'], '9993')  # original invocation retained

    def test_no_request_or_presentation_only_keeps_precision(self):
        for task in ['', 'Write briefly.', 'Round each to one decimal USD billion.',
                     'Do not round each to one decimal USD billion. Use the displayed one-decimal quarterly amounts for all calculations.',
                     TASK + ' Round each to two decimal USD billion.']:
            self.assertEqual(input_precision_policy(task), {})
        facts, metrics = plan(); facts[1].update(value='10.0', unit='USD billions')
        result = calculate_metrics(facts, metrics, SOURCES)
        self.assertEqual(result['facts'][0]['value'], '9.44')
        self.assertEqual(result['metrics'][0]['value'], '5.9')

    def test_fact_declaration_supports_explicit_normalization_without_recognized_prose(self):
        facts, metrics = plan()
        for f in facts: f['normalization'] = dict(unit='USD billions', decimal_places=1)
        result = calculate_metrics(facts, metrics, SOURCES)
        self.assertEqual(result['metrics'][0]['value'], '6.4')
        facts[0]['normalization']['decimal_places'] = 2
        with self.assertRaisesRegex(ValueError, 'conflicts'):
            calculate_metrics(facts, metrics, SOURCES, input_policy=input_precision_policy(TASK))

    def test_missing_values_negative_half_up_and_currency_rejection(self):
        spec = dict(unit='USD billions', decimal_places=1)
        self.assertEqual(normalize('-9450','USD millions', spec), '-9.5')
        self.assertIsNone(normalize(None,'USD millions', spec))
        with self.assertRaisesRegex(ValueError, 'currencies'): normalize('1','EUR billions', spec)
        facts, metrics = plan(); facts[1].update(value=None, citations=[])
        result = calculate_metrics(facts, metrics, SOURCES, input_policy=input_precision_policy(TASK))
        self.assertEqual(result['facts'][0]['value'], '9.4')
        self.assertEqual(result['metrics'][0]['status'], 'unavailable')

    def test_feedback_distinguishes_unit_from_numeric_mismatch(self):
        facts, metrics = plan(); result=calculate_metrics(facts, metrics, SOURCES, input_policy=input_precision_policy(TASK))
        text='| Revenue Q3 | 9.4 | [S1] |\n| Revenue Q4 | 10.0 | [S2] |\n\n| Metric | Result | Basis |\n|---|---|---|\n| Growth | 6.4 | (10-9.4)/9.4*100% |'
        def check(s): return validate_report(s, SOURCES, [{'result': result}], {})
        issue=check(text)['issues'][0]
        self.assertEqual(issue['code'],'missing_percent_unit')
        self.assertEqual(issue['expected_display'],'6.4%')
        self.assertTrue(check(text.replace('| Growth | 6.4 |','| Growth | 6.4% |'))['passed'])
        self.assertEqual(check(text.replace('| Growth | 6.4 |','| Growth | 5.9 |'))['issues'][0]['code'],'calculation_result_mismatch')
        issue=check(text.replace('| Revenue Q3 | 9.4 |','| Revenue Q3 | 9.44 |'))['issues'][0]
        self.assertIn('normalized fact value',issue['required_action'])

    def test_native_success_cannot_mask_empty_delivery_and_timeout_is_retained(self):
        for count, checks, expected in [(0, [], 'no_admitted_evidence'),(1, [], 'empty_report'),(1,[{'passed':False}], 'report_repair_exhausted')]:
            result=delivery_outcome('succeeded',None,'',False,source_count=count,validation_checks=checks)
            self.assertEqual((result['status'],result['native_status'],result['error_code']),('failed','succeeded',expected))
        result=delivery_outcome('timed_out','deadline','',False,source_count=1,validation_checks=[])
        self.assertEqual((result['status'],result['error_code']),('timed_out','deadline'))
        result=delivery_outcome('succeeded',None,'Partial report',False,source_count=1,validation_checks=[])
        self.assertEqual(result['delivery_status'],'delivered_with_failed_checks')

    def test_real_runtime_emits_actionable_feedback_then_accepts_percent_repair(self):
        from test_runtime_integration import ToolFake, message
        from langchain_core.messages import AIMessage
        from runtime_adapter import assemble, agent_input, REPORT_PATH
        from phase1_request_policy import ReportRequest, required_headings
        from run_report import DEFAULT_BUDGET
        from provenance import digest
        async def check():
            with tempfile.TemporaryDirectory() as td:
                out=Path(td); sources=[]
                for i in [1,2]:
                    text='Source revenue: '+('9.44 billion' if i==1 else '9993 million')
                    sources.append(dict(source_kind='web',document_id=f'd{i}',title=f'd{i}',source_url=f'https://example.org/{i}',retrieval_url=f'https://example.org/{i}',text=text,text_sha256=digest(text.encode()),char_start=0,char_end=len(text),chunk_id=f'd{i}',evidence_id=f'd{i}'))
                packet=dict(source_mode='web_only',uploaded=[],web=sources,retrieval={'mode':'frozen'})
                req=ReportRequest(task='Calculate growth. '+TASK,source_mode='web_only')
                report='\n\n'.join('## '+h+'\n\nRevenue supported [S1][S2].' for h in required_headings(req.structure))
                table='| Revenue Q3 | 9.4 | [S1] |\n| Revenue Q4 | 10.0 | [S2] |\n| Growth | 6.4 | Computed |\n'
                report=report.replace('## Sources',table+'\n## Sources')
                facts,metrics=plan()
                for fact,source in zip(facts,sources):fact['source_quote']=source['text']
                model=ToolFake(responses=[message('retrieve_web_documents',{},'r'),message('calculate_report_metrics',dict(facts=facts,metrics=metrics),'c'),message('write_file',dict(path=REPORT_PATH,content=report),'bad'),message('write_file',dict(path=REPORT_PATH,content=report.replace('| Growth | 6.4 |','| Growth | 6.4% |')),'good'),AIMessage(content='Report generated.')])
                runtime,evidence=assemble(out,req,None,[],[],None,DEFAULT_BUDGET,model=model,frozen_evidence=packet)
                result=await runtime.arun(agent_input(req));await runtime.aclose()
                self.assertEqual(result.status,'succeeded')
                self.assertEqual([x['passed'] for x in evidence.validation_checks],[False,True])
                self.assertEqual(evidence.validation_checks[0]['issues'][0]['code'],'missing_percent_unit')
                self.assertIn('6.4%',(out/'raw_report.md').read_text())
        asyncio.run(check())


if __name__ == '__main__': unittest.main()
