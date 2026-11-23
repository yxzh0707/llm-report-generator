import asyncio,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from report_calculations import calculate_metrics

SOURCES=[{'citation':f'[S{i}]'} for i in range(1,5)]
def facts(values):
    return [dict(id=f'Q{i}',value=v,unit='USD billions',period=f'Q{i} FY2024',citations=[f'[S{i}]'] if v is not None else []) for i,v in enumerate(values,1)]
def metric(id,op,inputs):return dict(id=id,operation=op,inputs=inputs,decimal_places=1)
PLAN=[metric('H1','sum',['Q1','Q2']),metric('H2','sum',['Q3','Q4']),
      metric('CHANGE','percent_change',['H1','H2']),metric('PEAK','argmax',['Q1','Q2','Q3','Q4'])]
def run_calc(values,plan=PLAN):return {r['id']:r for r in calculate_metrics(facts(values),plan,SOURCES)['metrics']}

class CalculationTests(unittest.TestCase):
    def test_meta_observed_addition_failures_and_chained_growth(self):
        r=run_calc(['36.5','39.1','40.6','48.4'])
        self.assertEqual([r[k]['value'] for k in ['H1','H2','CHANGE','PEAK']],['75.6','89.0','17.7','Q4'])
        self.assertEqual(r['CHANGE']['leaf_inputs'],['Q1','Q2','Q3','Q4'])
    def test_missing_first_half_does_not_block_second_half(self):
        r=run_calc([None,None,'88.3','96.5'])
        self.assertEqual(r['H2']['value'],'184.8')
        self.assertEqual(r['H2']['citations'],['[S3]','[S4]'])
        for id in ['H1','CHANGE','PEAK']:
            self.assertEqual(r[id]['status'],'unavailable')
            self.assertEqual(r[id]['missing_inputs'],['Q1','Q2'])
    def test_zero_is_observed_not_missing_and_zero_base_is_undefined(self):
        r=run_calc(['0','0','1','2'])
        self.assertEqual(r['H1']['value'],'0.0')
        self.assertEqual(r['H2']['value'],'3.0')
        self.assertEqual(r['CHANGE']['status'],'undefined_zero_baseline')
    def test_negative_growth_preserved(self):
        r=run_calc(['119.6','90.8','85.8','94.9'])
        self.assertEqual(r['CHANGE']['value'],'-14.1');self.assertEqual(r['PEAK']['value'],'Q1')
    def test_equal_extrema_return_tie_instead_of_invented_winner(self):
        r=run_calc(['1','2','2','1'])['PEAK']
        self.assertEqual(r['selected_ids'],['Q2','Q3']);self.assertTrue(r['tie'])
    def test_amd_largest_increment_is_q2_to_q3(self):
        p=[metric('D12','difference',['Q2','Q1']),metric('D23','difference',['Q3','Q2']),metric('D34','difference',['Q4','Q3']),metric('MAX_DELTA','argmax',['D12','D23','D34'])]
        r=run_calc(['5.5','5.8','6.8','7.7'],p)
        self.assertEqual(r['MAX_DELTA']['value'],'D23')
    def test_unknown_citation_blocks_affected_branch_only(self):
        f=facts(['1','2','3','4']);f[0]['citations']=['[S99]']
        r={x['id']:x for x in calculate_metrics(f,PLAN,SOURCES)['metrics']}
        self.assertEqual(r['H1']['status'],'blocked_invalid_input');self.assertEqual(r['H2']['value'],'7.0')
    def test_mixed_units_not_silently_added(self):
        f=facts(['1','2','3','4']);f[0]['unit']='USD millions'
        r={x['id']:x for x in calculate_metrics(f,PLAN,SOURCES)['metrics']}
        self.assertEqual(r['H1']['status'],'invalid_units_or_operand');self.assertEqual(r['H2']['value'],'7.0')
    def test_cycle_and_undeclared_missing_node_rejected(self):
        for p in [[metric('A','sum',['B']),metric('B','sum',['A'])],[metric('A','sum',['MISSING'])]]:
            with self.assertRaises(ValueError):run_calc(['1','2','3','4'],p)
    def test_unbounded_or_code_like_values_are_not_executed(self):
        for value in ['NaN','Infinity','1e100000','__import__("os")','9'*1000,True,1.2]:
            with self.assertRaises(ValueError):run_calc([value,'2','3','4'])
    def test_rounding_is_decimal_half_up_and_composable(self):
        p=[metric('A','sum',['Q1','Q2']),metric('B','sum',['A','Q3'])]
        r=run_calc(['0.05','0','0.05','1'],p)
        self.assertEqual(r['A']['value'],'0.1');self.assertEqual(r['B']['value'],'0.2')

class RuntimeCalculationTests(unittest.TestCase):
    def test_tool_result_reaches_runtime_and_is_recorded(self):
        from test_runtime_integration import ToolFake,message
        from langchain_core.messages import AIMessage
        from runtime_adapter import assemble,agent_input,REPORT_PATH
        from phase1_request_policy import ReportRequest,required_headings
        from run_report import DEFAULT_BUDGET
        from provenance import digest
        async def check():
            with tempfile.TemporaryDirectory() as directory:
                out=Path(directory);text='Q3 revenue 88.3; Q4 revenue 96.5.'
                s=dict(source_kind='web',document_id='q34',title='Release',source_url='https://example.org',retrieval_url='https://example.org',text=text,text_sha256=digest(text.encode()),char_start=0,char_end=len(text),chunk_id='a',evidence_id='a')
                packet=dict(source_mode='web_only',uploaded=[],web=[s],retrieval={'mode':'frozen'})
                req=ReportRequest(task='Calculate H2 from Q3 and Q4, and disclose missing H1.',source_mode='web_only')
                f=facts([None,None,'88.3','96.5']);f[2]['citations']=f[3]['citations']=['[S1]']
                report='\n\n'.join('## '+h+'\n\nH2 revenue 184.8; H1 unavailable [S1].' for h in required_headings(req.structure))
                model=ToolFake(responses=[message('retrieve_web_documents',{},'retrieve'),message('calculate_report_metrics',{'facts':f,'metrics':PLAN},'calc'),message('write_file',{'path':REPORT_PATH,'content':report},'save'),AIMessage(content='Report generated.')])
                runtime,evidence=assemble(out,req,None,[],[],None,DEFAULT_BUDGET,model=model,frozen_evidence=packet,calculation_control='tool',report_validation='off')
                result=await runtime.arun(agent_input(req));await runtime.aclose()
                self.assertEqual(result.status,'succeeded',result.terminal)
                calls=json.loads((out/'calculation_calls.json').read_text())
                self.assertEqual(calls[0]['result']['metrics'][1]['value'],'184.8')
                self.assertEqual((out/'raw_report.md').read_text(),report)
                self.assertTrue(any(e.type=='model_input_captured' and '184.8' in json.dumps(e.data) for e in result.trajectory))
        asyncio.run(check())

if __name__=='__main__':unittest.main()
