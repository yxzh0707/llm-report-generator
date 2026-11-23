import asyncio
import copy
import json
import tempfile
import unittest
from pathlib import Path
from decimal import Decimal
from unittest.mock import patch

from fact_grounding import validate_fact_inputs, quoted_numbers
from report_periods import compare_periods, validate_calendar_claims, dates_in
from report_revision import section_budgets
from fact_repair import validate_requested_basis, source_candidates
from report_edits import apply_edits, editable_blocks
from report_editor import focused_edit_payload
from report_coverage import validate_missing_topics,business_topics


class GroundingTests(unittest.TestCase):
    def setUp(self):
        self.sources=[dict(citation='[S1]',text='Results (USD in millions). Revenue 12,345. Period ended January 31, 2025.'),
                      dict(citation='[S2]',text='Results. Revenue was $7.8 billion. Period ended November 28, 2025.')]
        self.fact=dict(id='r',value='12345',unit='USD millions',citations=['[S1]'],
                       source_quote='Revenue 12,345.',unit_quote='USD in millions')

    def test_original_token_and_same_source_scale_are_required(self):
        check=lambda f:validate_fact_inputs([f],self.sources)
        self.assertTrue(check(self.fact)['passed'])
        for changes,code in [({'value':'12.35','unit':'USD billions'},'raw_value_not_in_quote'),
                             ({'unit':'USD billions'},'raw_unit_not_in_quote'),
                             ({'citations':['[S2]']},'raw_quote_not_in_cited_source'),
                             ({'unit_quote':'USD in billions'},'raw_quote_not_in_cited_source'),
                             ({'source_quote':None},'raw_source_quote_required'),
                             ({'unit':'EUR millions'},'raw_currency_conflict')]:
            result=check({**self.fact,**changes})
            self.assertFalse(result['passed']);self.assertEqual(result['issues'][0]['code'],code)

    def test_disclosed_headline_and_missing_input_remain_valid(self):
        headline=dict(self.fact,value='7.8',unit='USD billions',citations=['[S2]'],
                      source_quote='Revenue was $7.8 billion.',unit_quote='')
        self.assertTrue(validate_fact_inputs([headline,dict(id='absent',value=None)],self.sources)['passed'])
        self.assertEqual(list(quoted_numbers('Revenue (1,234.5); EPS -0.2.')), [Decimal('-1234.5'),Decimal('-0.2')])
        self.assertEqual(list(quoted_numbers('Q3 FY2025 12.34.')), [Decimal('12.34')])

    def test_typography_is_repaired_without_changing_evidence_numbers(self):
        sources=[dict(citation='[S1]',text='Revenue of $7.8 billion, up 9% (“Y/Y”).')]
        f=dict(id='r',value='7.8',unit='USD billions',citations=['[S1]'],source_quote='Revenue of $7.8 billion, up 9% ("Y/Y").',unit_quote='Revenue (USD billions)')
        result=validate_fact_inputs([f],sources)
        self.assertTrue(result['passed']);self.assertEqual(result['checks'][0]['source_quote'],sources[0]['text'])
        self.assertTrue(result['checks'][0]['redundant_unit_quote_ignored'])
        self.assertEqual(result['checks'][0]['unit_quote'],'')
        self.assertFalse(validate_fact_inputs([{**f,'value':'7.9'}],sources)['passed'])
        self.assertFalse(validate_fact_inputs([{**f,'source_quote':f['source_quote'].replace('up','down')}],sources)['passed'])

    def test_explicit_metric_scope_checks_row_not_company_or_answer_key(self):
        task='For WarehouseCo include membership fees and for ShopCo use reported net sales.'
        quote='Net sales 8,000 7,000 Membership fees 200 180 Total revenue 8,200 7,180 Operating expenses'
        f=dict(id='x',report_label='WarehouseCo Q3 revenue',value='8000',source_quote=quote)
        self.assertTrue(validate_requested_basis([f],task))
        self.assertEqual(validate_requested_basis([{**f,'value':'8200'}],task),[])
        self.assertEqual(validate_requested_basis([{**f,'report_label':'ShopCo Q3 revenue'}],task),[])
        self.assertEqual(validate_requested_basis([f],'Compare net sales.'),[])
        self.assertEqual(validate_requested_basis([{**f,'value':None}],task),[])

    def test_repair_hints_are_literal_source_rows_with_column_context(self):
        source=dict(citation='[S1]',document_id='warehouse',text='Quarter results (in millions). Q3 2025 Q3 2024. Net sales 8,000 7,000 Membership fees 200 180 Total revenue 8,200 7,180 Operating expenses 4,000 3,800.')
        fact=dict(id='x',report_label='WarehouseCo Q3 revenue',value='8000',citations=['[S1]'])
        hints=source_candidates(fact,[source],'For WarehouseCo include membership fees.')
        self.assertTrue(hints[0]['source_quote'].startswith('Total revenue 8,200'))
        self.assertIn('Q3 2025 Q3 2024',hints[0]['preceding_context'])
        for h in hints:
            self.assertIn(h['source_quote'],source['text']);self.assertIn(h['unit_quote'],source['text'])
        self.assertEqual(source_candidates({**fact,'citations':['[S99]']},[source]),[])

    def test_real_runtime_rejects_prerounding_then_uses_original_source(self):
        from test_runtime_integration import ToolFake, message
        from langchain_core.messages import AIMessage
        from runtime_adapter import assemble, agent_input, REPORT_PATH
        from phase1_request_policy import ReportRequest, required_headings
        from run_report import DEFAULT_BUDGET
        from provenance import digest
        async def run():
            with tempfile.TemporaryDirectory() as td:
                out=Path(td);sources=[]
                for i,s in enumerate(self.sources,1):
                    text=s['text'];identity=f'd{i}'
                    sources.append(dict(source_kind='web',document_id=identity,title=identity,
                        source_url=f'https://example.org/{i}',retrieval_url=f'https://example.org/{i}',
                        text=text,text_sha256=digest(text.encode()),char_start=0,char_end=len(text),chunk_id=identity,evidence_id=identity))
                facts=[{**self.fact,'period':'Q3 FY2025','report_label':'A revenue'},
                       dict(id='b',value='7.8',unit='USD billions',period='Q4 FY2025',citations=['[S2]'],
                            report_label='B revenue',source_quote='Revenue was $7.8 billion.')]
                metrics=[dict(id='total',operation='sum',inputs=['r','b'],decimal_places=2,report_label='Combined revenue')]
                for f in facts:f['normalization']=dict(unit='USD billions',decimal_places=3)
                bad=copy.deepcopy(facts);bad[0].update(value='12.3',unit='USD billions')
                req=ReportRequest(task='Calculate combined revenue. Display USD billions to two decimal places.',source_mode='web_only')
                # Display rounding does not round inputs: 12.345+7.8 = 20.145 -> 20.15.
                table='| A revenue | 12.35 USD billions | [S1] |\n| B revenue | 7.80 USD billions | [S2] |\n| Combined revenue | 20.15 USD billions | Calculated |'
                report='\n\n'.join('## '+h+'\n\n'+(table if h=='Key Findings' else 'Reported evidence [S1][S2].') for h in required_headings(req.structure))
                fake=ToolFake(responses=[message('retrieve_web_documents',{},'read'),
                    message('calculate_report_metrics',dict(facts=bad,metrics=metrics),'bad'),
                    message('calculate_report_metrics',dict(facts=facts,metrics=metrics),'fixed'),
                    message('write_file',dict(path=REPORT_PATH,content=report),'save'),AIMessage(content='Report generated.')])
                runtime,evidence=assemble(out,req,None,[],[],None,DEFAULT_BUDGET,model=fake,
                    frozen_evidence=dict(source_mode='web_only',uploaded=[],web=sources,retrieval={'mode':'frozen'}))
                result=await runtime.arun(agent_input(req));await runtime.aclose()
                self.assertEqual(result.status,'succeeded',result.terminal)
                self.assertIn('error',evidence.calculation_calls[0]['result'])
                self.assertNotIn('error',evidence.calculation_calls[1]['result'])
                self.assertEqual(evidence.calculation_calls[1]['result']['metrics'][0]['value'],'20.15')
                self.assertTrue((out/'raw_report.md').exists())
                self.assertEqual(len(evidence.calculation_revision_events),1)
                inputs=[e.data for e in result.trajectory if e.type=='model_input_captured' and e.data.get('model_call')==3]
                self.assertEqual(inputs[0]['request_contract']['tools'],['calculate_report_metrics'])
                self.assertIn('repair_calculation_inputs_from_exact_source_spans',json.dumps(inputs[0]))
        asyncio.run(run())


class PeriodTests(unittest.TestCase):
    def test_date_arithmetic_and_quantified_claim_gate(self):
        sources=[dict(citation='[S1]',text='Alpha period ended January 31, 2025.'),
                 dict(citation='[S2]',text='Beta period ended Nov. 28, 2025.')]
        periods=[dict(id='a',label='Alpha Q4',end_date='2025-01-31',citation='[S1]',source_quote=sources[0]['text']),
                 dict(id='b',label='Beta Q4',end_date='2025-11-28',citation='[S2]',source_quote=sources[1]['text'])]
        result=compare_periods(periods,[dict(left='a',right='b')],sources)
        self.assertEqual(result['comparisons'][0]['absolute_days'],301)
        calls=[dict(result=result)]
        self.assertTrue(validate_calendar_claims('Alpha and Beta fiscal periods are offset by roughly two calendar quarters.',calls))
        self.assertFalse(validate_calendar_claims('Alpha and Beta fiscal periods are 301 days apart.',calls))
        self.assertFalse(validate_calendar_claims('Alpha and Beta fiscal periods are offset by roughly ten months.',calls))
        self.assertTrue(validate_calendar_claims('Alpha and Beta fiscal periods are 301 days apart.',[]))
        for s in ['Revenue grew 10% in the quarter.','The reporting quarter has 13 weeks.','The fiscal periods end January 31 and November 28, 2025.']:
            self.assertEqual(validate_calendar_claims(s,[]),[])
        periods[0]['end_date']='2025-01-30'
        with self.assertRaisesRegex(ValueError,'must occur'):compare_periods(periods,[dict(left='a',right='b')],sources)

    def test_invalid_dates_and_wrong_source(self):
        self.assertEqual(len(dates_in('2025-02-30; September 30, 2025; Sept. 30, 2025; 2025-09-30')),1)
        with self.assertRaisesRegex(ValueError,'not in the cited'):
            compare_periods([dict(id=x,label=x,end_date='2025-01-31',citation='[S1]',source_quote='January 31, 2025') for x in ['a','b']],
                            [dict(left='a',right='b')],[dict(citation='[S1]',text='January 30, 2025')])

    def test_duration_heading_and_multiple_period_pairs(self):
        for line in ['**Fiscal-calendar differences:** Alpha Q3 is 12 weeks, Q4 is 16 weeks.',
                     '**Fiscal differences:** Alpha Q3 ended May 11, 2025 (12 weeks).']:
            self.assertEqual(validate_calendar_claims(line,[]),[])
        calls=[dict(result=dict(comparisons=[dict(left='Alpha Q3 FY2025',right='Beta Q3 FY2025',absolute_days=174),
                                             dict(left='Alpha Q4 FY2025',right='Beta Q4 FY2025',absolute_days=153)]))]
        text='Alpha and Beta Q3 period ends differ by 174 days. Alpha and Beta Q4 period ends differ by 153 days.'
        self.assertEqual(validate_calendar_claims(text,calls),[])
        self.assertTrue(validate_calendar_claims(text.replace('174','153'),calls))
        comma='Alpha and Beta fiscal periods differ: Q3 ends are 174 days apart and Q4 ends are 153 days apart.'
        self.assertEqual(validate_calendar_claims(comma,calls),[])
        self.assertTrue(validate_calendar_claims(comma.replace('Q3 ends are 174','Q3 ends are 153'),calls))


class RevisionTests(unittest.TestCase):
    def test_editor_selects_scope_block_and_local_budget(self):
        from phase1_request_policy import ReportRequest
        draft='## Comparison Scope and Criteria\n\n'+'Scope statement with repeated wording. '*15+'\n\n## Comparison by Dimension\n\n'+'Required business details and qualifications. '*30+'\n\n## Sources\n[S1] Reference'
        p=focused_edit_payload(ReportRequest(task='Compare the companies.'),draft,dict(body_words=300,maximum_words=200))
        self.assertEqual(p['section'],'Comparison Scope and Criteria')
        self.assertLess(p['target_block_words'],p['current_block_words']/2)
        self.assertNotIn('Required business details',p['selected_blocks'][0]['text'])
        self.assertEqual(len(p['selected_blocks']),2)
        self.assertNotIn('latest_draft',p)
        p2=focused_edit_payload(ReportRequest(task='Compare the companies.'),draft,dict(body_words=300,maximum_words=200),history=[{'section':p['section']}]*2)
        self.assertEqual(p2['section'],'Comparison by Dimension')

    def test_editor_batches_only_for_large_measured_excess(self):
        from phase1_request_policy import ReportRequest
        draft='\n\n'.join('## Section '+str(i)+'\n\n'+'Retain this supported explanation with its period and attribution. '*10 for i in range(4))
        req=ReportRequest(task='Explain the supplied evidence.')
        large=focused_edit_payload(req,draft,dict(body_words=800,maximum_words=600))
        small=focused_edit_payload(req,draft,dict(body_words=620,maximum_words=600))
        self.assertEqual(len(large['selected_blocks']),3)
        self.assertEqual(len(small['selected_blocks']),1)
        self.assertEqual(len({b['block_id'] for b in large['selected_blocks']}),3)

    def test_exact_edits_preserve_structure_quantities_and_sources(self):
        draft='## Findings\nRevenue was 12.35 billion, according to the cited report [S1].\n| Metric | 12.35 |\n## Conclusion\nThe reported result was positive.\n## Sources\n[S1] source'
        edits=[dict(old='Revenue was 12.35 billion, according to the cited report [S1].',new='Revenue: 12.35 billion [S1].')]
        revised=apply_edits(draft,edits);self.assertIn('Revenue: 12.35 billion [S1].',revised)
        block=next(b for b in editable_blocks(draft) if b['text'].startswith('The reported'))
        self.assertIn('Positive result.',apply_edits(draft,[dict(block_id=block['block_id'],new='Positive result.')]))
        for old,new in [('12.35 billion','13.35'),('## Findings',''),('| Metric | 12.35 |',''),('not present','short')]:
            with self.assertRaises(ValueError):apply_edits(draft,[dict(old=old,new=new)])

    def test_edit_tool_passes_through_the_normal_save_gate(self):
        from test_runtime_integration import ToolFake,message
        from langchain_core.messages import AIMessage
        from runtime_adapter import assemble,agent_input,REPORT_PATH
        from phase1_request_policy import ReportRequest,required_headings
        from run_report import DEFAULT_BUDGET
        async def run():
            with tempfile.TemporaryDirectory() as td:
                root=Path(td);corpus=root/'corpus';corpus.mkdir();(corpus/'a.md').write_text('Revenue grew 10 percent.')
                out=root/'out';out.mkdir();req=ReportRequest(task='Summarise revenue',max_words=100)
                long='Additional context without any new unsupported assertion. '*30
                report='\n\n'.join('## '+h+'\n\nReported revenue [S1].' for h in required_headings(req.structure))
                report=report.replace('## Sources',long+'\n\n## Sources')
                block=next(b for b in editable_blocks(report) if long.strip() in b['text'])
                fake=ToolFake(responses=[message('retrieve_uploaded_documents',{},'r'),
                    message('write_file',dict(path=REPORT_PATH,content=report),'over'),
                    message('revise_report_text',dict(replacements=[dict(block_id=block['block_id'],new='Brief supporting context.')]),'edit'),AIMessage(content='Report generated.')])
                runtime,evidence=assemble(out,req,corpus,['a'],['revenue'],None,DEFAULT_BUDGET,model=fake)
                result=await runtime.arun(agent_input(req));await runtime.aclose()
                self.assertEqual(result.status,'succeeded',result.terminal)
                self.assertEqual((out/'raw_report.md').read_text(),report[:block['start']]+'Brief supporting context.'+report[block['end']:])
                self.assertEqual([x['can_save'] for x in evidence.length_checks],[False,True])
                self.assertTrue(evidence.validation_checks[-1]['passed'])
                self.assertEqual(len(evidence.revision_edits),1)
        with patch('runtime_adapter.ReportTokenMeter.measure',return_value=dict(count=None,exact_for_text=False,method='unavailable')):
            asyncio.run(run())


class MissingTopicTests(unittest.TestCase):
    TASK='Explain these business topics from the Q4 releases: WarehouseCo: online comparable sales growth; ShopCo: membership delivery growth. Retain the original period.'
    CALLS=[dict(result=dict(facts=[dict(status='unavailable',value=None,period='Q4 FY2025',report_label='ShopCo Q4 revenue')]))]
    SOURCES=[dict(title='ShopCo Q3 FY2025 release',fiscal_year=2025,fiscal_quarter=3)]

    def test_prior_quarter_and_financial_disclosure_do_not_replace_topic(self):
        bad='ShopCo Q4 revenue and H2 revenue are Unavailable because the release is absent.\nShopCo Q3 membership delivery growth was 35%.'
        issues=validate_missing_topics(bad,self.TASK,self.CALLS,self.SOURCES)
        self.assertEqual([i['code'] for i in issues],['missing_business_topic_disclosure'])
        good=bad+'\nShopCo Q4 membership delivery growth cannot be established because its release is absent.'
        self.assertEqual(validate_missing_topics(good,self.TASK,self.CALLS,self.SOURCES),[])
        self.assertEqual(len(business_topics(self.TASK)),2)

    def test_heading_context_and_available_source(self):
        good='### ShopCo Q4 membership delivery\nThe requested update cannot be established: the release is missing.'
        self.assertEqual(validate_missing_topics(good,self.TASK,self.CALLS,self.SOURCES),[])
        available=self.SOURCES+[dict(title='ShopCo Q4 FY2025 release',fiscal_year=2025,fiscal_quarter=4)]
        self.assertEqual(validate_missing_topics('',self.TASK,self.CALLS,available),[])
        self.assertEqual(validate_missing_topics('','Summarize available materials.',self.CALLS,self.SOURCES),[])

    def test_budgets_preserve_tables_and_ignore_sources(self):
        draft='# Title\n## Findings\n| Revenue | 12.35 | [S1] |\n'+'narrative '*100+'\n## Conclusion\n'+'summary '*30+'\n## Sources\n'+'source '*1000
        budget=section_budgets(draft,80)
        self.assertEqual([s['section'] for s in budget['sections']],['Findings','Conclusion'])
        self.assertLessEqual(sum(s['draft_budget_words'] for s in budget['sections']),80)
        self.assertGreater(budget['sections'][0]['reserved_heading_table_words'],1)

    def test_identical_rejected_draft_stops_before_budget_exhaustion(self):
        from test_runtime_integration import ToolFake,message
        from runtime_adapter import assemble,agent_input,REPORT_PATH
        from phase1_request_policy import ReportRequest,required_headings
        from run_report import DEFAULT_BUDGET
        async def run():
            with tempfile.TemporaryDirectory() as td:
                root=Path(td);corpus=root/'corpus';corpus.mkdir();(corpus/'a.md').write_text('Revenue evidence')
                out=root/'out';out.mkdir();req=ReportRequest(task='Summarise revenue',max_words=100)
                report='\n\n'.join('## '+h+'\n\n'+'Supported evidence [S1]. '*25 for h in required_headings(req.structure))
                fake=ToolFake(responses=[message('retrieve_uploaded_documents',{},'r')]+[
                    message('write_file',dict(path=REPORT_PATH,content=report),str(i)) for i in range(12)])
                runtime,evidence=assemble(out,req,corpus,['a'],['revenue'],None,DEFAULT_BUDGET,model=fake)
                result=await runtime.arun(agent_input(req));await runtime.aclose()
                self.assertEqual(result.status,'failed')
                self.assertEqual(len(evidence.length_checks),4)
                self.assertEqual(len(evidence.length_revision_events),3)
                self.assertFalse((out/'raw_report.md').exists())
        with patch('runtime_adapter.ReportTokenMeter.measure',return_value=dict(count=None,exact_for_text=False,method='unavailable')):
            asyncio.run(run())
