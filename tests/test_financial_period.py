import asyncio,copy,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from financial_period import select_sec_facts,validate_financial_scope
from finance_evidence import bounded_arguments
SCOPE=dict(identifier='1',concept='Revenues',unit='USD',as_of='2025-03-31',periods=[{'id':'quarter','start':'2024-07-01','end':'2024-09-30'},{'id':'ytd','start':'2024-01-01','end':'2024-09-30'}])
ARGS=dict(identifier='1',concept='Revenues',before='2025-03-31',limit=100)
def row(**kw):return dict(unit='USD',start='2024-07-01',end='2024-09-30',val=30,accn='a',filed='2024-11-01',fy=2025,fp='FY',frame='CY2024Q3',**{})|kw
def payload(rows):return dict(cik='0000000001',concept='Revenues',entity='Fixture',facts=rows)
def select(rows,scope=SCOPE):return select_sec_facts('sec_company_facts',ARGS,payload(rows),scope)
class FinancialPeriodTests(unittest.TestCase):
 def test_exact_duration_not_filing_focus_or_end_only(self):
  rows=[row(),row(start='2024-01-01',val=90),row(start='2023-07-01',end='2023-09-30',val=20),row(start='2024-01-01',end='2024-12-31',val=120)]
  result,a=select(rows);self.assertEqual([r['val'] for r in result['facts']],[30,90]);self.assertEqual(a['selected_records'],2)
 def test_filing_asof_and_units(self):
  result,a=select([row(),row(filed='2025-04-01',val=31),row(unit='EUR',val=32)])
  self.assertEqual(result['facts'][0]['val'],30);self.assertEqual([x['reason'] for x in a['decisions']][1:],['filed_after_as_of','unit_not_requested'])
 def test_latest_asof_duplicates_not_additive(self):
  rows=[row(val=29),row(filed='2025-01-01',accn='b'),row(filed='2025-01-01',accn='c')];before=copy.deepcopy(rows)
  result,a=select(rows);self.assertEqual(len(result['facts']),1);self.assertEqual(result['facts'][0]['accn'],'b');self.assertEqual(rows,before)
 def test_conflict_not_hidden_by_earlier_value(self):
  result,a=select([row(val=29),row(filed='2025-01-01'),row(filed='2025-01-01',accn='b',val=31)])
  self.assertEqual(result['facts'],[]);self.assertEqual(a['availability'][0]['reason'],'conflicting_values_same_latest_date')
 def test_invalid_rows_and_future_date_not_used(self):
  for change in [{'filed':'unknown'},{'val':float('nan')},{'val':True},{'start':'2024-10-01'},{'accn':''}]:
   _,a=select([row(**change)]);self.assertEqual(a['decisions'][0]['decision'],'quarantine')
 def test_instant_not_duration(self):
  s={**SCOPE,'periods':[{'id':'assets','end':'2024-09-30'}]};r=row();r.pop('start')
  result,a=select([r,row()],s);self.assertEqual(result['facts'],[r])
 def test_issuer_concept_and_unsupported_api_fail_closed(self):
  for args,value,name in [(dict(ARGS,identifier='2'),payload([row()]),'sec_company_facts'),(ARGS,dict(payload([row()]),concept='Assets'),'sec_company_facts'),(ARGS,payload([row()]),'alpha_vantage')]:
   with self.assertRaises(ValueError):select_sec_facts(name,args,value,SCOPE)
 def test_scope_and_independent_fetch_limit_validation(self):
  for scope in [{**SCOPE,'as_of':'2025'},{**SCOPE,'periods':SCOPE['periods']*2},{**SCOPE,'identifier':'NVDA'}]:
   with self.assertRaises(ValueError):validate_financial_scope(scope)
  self.assertEqual(bounded_arguments('sec_company_facts',ARGS)['limit'],12)
  self.assertEqual(bounded_arguments('sec_company_facts',ARGS,sec_fact_limit=100)['limit'],100)
  self.assertEqual(bounded_arguments('sec_filings',{'limit':100},sec_fact_limit=100)['limit'],5)
 def test_adapter_filters_before_projection_and_empty_data_not_admitted(self):
  from runtime_adapter import ReportEvidenceMiddleware
  from run_report import DEFAULT_BUDGET
  from phase1_request_policy import ReportRequest
  async def check():
   rows=[row(start='2020-01-01',end='2020-03-31',accn=str(i)) for i in range(98)]+[row(),row(start='2024-01-01',val=90)]
   for mode in ['off','enforce']:
    with tempfile.TemporaryDirectory() as folder:
     p=Path(folder);replay={json.dumps({'name':'sec_company_facts','arguments':ARGS},sort_keys=True):payload(rows)}
     m=ReportEvidenceMiddleware(p,ReportRequest(task='test',source_mode='web_only'),None,[],[],None,DEFAULT_BUDGET,web_replay=replay,financial_period_scope=SCOPE,financial_period_filter=mode,sec_fact_limit=100)
     r=json.loads(await m._call('sec_company_facts',ARGS));facts=json.loads(r['text'])['data']['facts']
     self.assertEqual(any(x['end']=='2024-09-30' for x in facts),mode=='enforce')
     self.assertEqual(json.loads((p/'financial_response_001.txt').read_text())['facts'],rows)
   with tempfile.TemporaryDirectory() as folder:
    p=Path(folder);r={json.dumps({'name':'sec_company_facts','arguments':ARGS},sort_keys=True):payload(rows[:98])}
    m=ReportEvidenceMiddleware(p,ReportRequest(task='test',source_mode='web_only'),None,[],[],None,DEFAULT_BUDGET,web_replay=r,financial_period_scope=SCOPE,financial_period_filter='enforce',sec_fact_limit=100)
    self.assertIn('error',json.loads(await m._call('sec_company_facts',ARGS)));self.assertFalse(m.sources);self.assertTrue((p/'financial_period_checks.json').exists())
  asyncio.run(check())
if __name__=='__main__':unittest.main()
