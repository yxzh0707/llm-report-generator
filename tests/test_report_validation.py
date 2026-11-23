import asyncio,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from report_validation import citation_id,source_policy,source_period,fiscal_period,validate_report,requests_calculation
from report_calculations import calculate_metrics
from test_report_calculations import facts,PLAN,metric

SOURCES=[dict(citation=f'[S{i}]',title=f'Q{i} FY2024',fiscal_year=2024,fiscal_quarter=i) for i in range(1,5)]
def labelled(values):
 f=facts(values)
 for x in f:x['report_label']=x['period']
 m=[dict(x,report_label=label) for x,label in zip(PLAN,['H1 revenue','H2 revenue','H2 vs H1 revenue change','Highest-revenue quarter'])]
 return f,m
def report_for(values,results):
 rows=['| Fiscal quarter | Revenue (USD billions) | Evidence |','|---|---|---|']
 rows += [f'| Q{i} FY2024 | {v if v is not None else "Unavailable"} | {["", "[S1]", "[S2]", "[S3]", "[S4]"][i] if v is not None else ""} |' for i,v in enumerate(values,1)]
 rows += ['','| Metric | Result | Basis |','|---|---|---|']
 for n in results['metrics']:
  v=n['value'] if n['status']=='available' else 'Unavailable'
  if n.get('unit')=='percent' and n['status']=='available':v+='%'
  rows.append(f'| {n["report_label"]} | {v} | Calculated |')
 return '\n'.join(rows)

class ValidationTests(unittest.TestCase):
 def test_canonical_table_does_not_compare_source_notes_or_equations(self):
  f,m=labelled(['1','2','3','4']);r=calculate_metrics(f,m,SOURCES)
  text=report_for(['1','2','3','4'],r)+'\nQ1 FY2024: uploaded release dated April25,2024 [S1].\nH1 revenue: 1 + 2 = 3.0 USD billions.'
  self.assertTrue(validate_report(text,SOURCES,[{'result':r}],{})['passed'])
  self.assertFalse(validate_report(text.replace('| H1 revenue | 3.0','| H1 revenue | 2.0'),SOURCES,[{'result':r}],{})['passed'])
 def test_duplicate_bad_table_cannot_hide_behind_correct_table(self):
  f,m=labelled(['1','2','3','4']);r=calculate_metrics(f,m,SOURCES)
  text=report_for(['1','2','3','4'],r)+'\n| H1 revenue | 2.0 | Incorrect |'
  self.assertFalse(validate_report(text,SOURCES,[{'result':r}],{})['passed'])
 def test_aliases_stay_bound_to_known_ids(self):
  f,m=labelled(['1','2','3','4']);f[0]['citations']=['S1']
  self.assertEqual(calculate_metrics(f,m,SOURCES)['facts'][0]['status'],'available')
  f[0]['citations']=['S99'];self.assertEqual(calculate_metrics(f,m,SOURCES)['facts'][0]['status'],'invalid_source')
  self.assertEqual(citation_id('[S1'),'[S1')
 def test_explicit_rule_and_fiscal_titles_not_publication_date(self):
  self.assertTrue(source_policy("Use each quarter's own release.")['own_quarter_release'])
  self.assertFalse(source_policy('Compare quarterly figures using the available releases.')['own_quarter_release'])
  for title,period in [('FY24 Q3 - Microsoft',(2024,3)),('NVIDIA Fourth Quarter and Fiscal 2025',(2025,4)),('AMD Third Quarter 2024 Financial Results',(2024,3))]:self.assertEqual(fiscal_period(title),period)
  self.assertIsNone(source_period({'title':'Annual update','publication_date':'2024-04-25','text':'Q1 FY2024 and Q2 FY2024'}))
 def test_later_release_allowed_unless_user_forbids_it(self):
  f,m=labelled(['1','2','3','4']);f[1]['citations']=['[S3]']
  self.assertEqual(calculate_metrics(f,m,SOURCES)['facts'][1]['status'],'available')
  r=calculate_metrics(f,m,SOURCES,policy={'own_quarter_release':True})
  self.assertEqual(r['facts'][1]['status'],'ineligible_source_period')
  self.assertEqual(r['metrics'][0]['status'],'blocked_invalid_input')
  self.assertEqual(r['metrics'][1]['value'],'7.0')
 def test_unknown_source_period_is_not_silently_verified(self):
  f,m=labelled(['1','2','3','4']);s=[{'citation':s['citation'],'title':'Unlabelled release'} for s in SOURCES]
  r=calculate_metrics(f,m,s,policy={'own_quarter_release':True})
  self.assertEqual(r['facts'][0]['status'],'ineligible_source_period')
 def test_mismatched_saved_value_and_missing_metric_denied(self):
  f,m=labelled(['36.5','39.1','40.6','48.4']);result=calculate_metrics(f,m,SOURCES)
  text=report_for(['36.5','39.1','40.6','48.4'],result)
  check=lambda s:validate_report(s,SOURCES,[{'result':result}],{'own_quarter_release':True})
  self.assertTrue(check(text)['passed'])
  self.assertFalse(check(text.replace('| H1 revenue | 75.6','| H1 revenue | 75.5'))['passed'])
  self.assertFalse(check('\n'.join(l for l in text.splitlines() if not l.startswith('| H2 revenue')))['passed'])
 def test_correct_number_wrong_currency_or_header_unit_denied(self):
  f,m=labelled(['1','2','3','4']);r=calculate_metrics(f,m,SOURCES);text=report_for(['1','2','3','4'],r)
  for wrong in [text.replace('USD billions','USD millions'),text.replace('| H1 revenue | 3.0','| H1 revenue | EUR 3.0')]:self.assertFalse(validate_report(wrong,SOURCES,[{'result':r}],{})['passed'])
 def test_forged_quarter_row_denied_even_without_calculation_binding(self):
  text='| Q2 FY2024 | 30.0 | [S3] |'
  self.assertFalse(validate_report(text,SOURCES,[],{'own_quarter_release':True})['passed'])
  self.assertTrue(validate_report(text,SOURCES,[],{})['passed'])
 def test_unavailable_rows_and_labelled_lines(self):
  f,m=labelled([None,None,'3','4']);r=calculate_metrics(f,m,SOURCES)
  text=report_for([None,None,'3','4'],r)
  self.assertTrue(validate_report(text,SOURCES,[{'result':r}],{'own_quarter_release':True})['passed'])
  self.assertFalse(validate_report(text.replace('| H2 revenue | 7.0','| H2 revenue | Unavailable'),SOURCES,[{'result':r}],{})['passed'])
  self.assertTrue(validate_report('H2 revenue: 7.0 USD billions',SOURCES,[{'result':{'metrics':[r['metrics'][1]]}}],{})['passed'])
 def test_negated_calculation_request_not_forced(self):
  self.assertFalse(requests_calculation('Summarise. Do not calculate ratios.'))
  self.assertTrue(requests_calculation('Calculate H2. Do not calculate ratios.'))
 def test_unavailable_explanation_year_is_not_a_revenue(self):
  policy={'own_quarter_release':True}
  text='- Q1 FY2024 revenue is Unavailable: the contemporaneous Q1 FY2024 release is not in the permitted evidence set.'
  self.assertTrue(validate_report(text,SOURCES,[],policy)['passed'])
  for value in ['26.0 billion [S3]','$26.0 billion [S3]','**USD 26.0 billion** [S3]']:
   self.assertFalse(validate_report('Q1 FY2024 revenue is Unavailable: '+value,SOURCES,[],policy)['passed'])
 def test_bad_tool_input_cannot_be_hidden_as_unavailable(self):
  f,m=labelled(['1','2','3','4']);f[0]['citations']=['[S99]'];r=calculate_metrics(f,m,SOURCES)
  self.assertFalse(validate_report(report_for(['1','2','3','4'],r),SOURCES,[{'result':r}],{})['passed'])
 def test_parenthetical_original_units_do_not_conflict_with_leading_quantity(self):
  from report_validation import result_matches
  node={'status':'available','value':'80.5','unit':'USD billions'}
  self.assertTrue(result_matches('$80.5 billion (reported $80,539 million)',node))
  self.assertFalse(result_matches('$80.5 million (reported $80.5 billion)',node))
  self.assertFalse(result_matches('$80.5 billion (reported $80,539 million)',node,'USD millions'))
 def test_explicit_missing_release_explanations_not_numeric_assertions(self):
  from report_validation import result_matches
  node={'status':'unavailable','value':None}
  for text in ['no own contemporaneous release in the permitted set; later release is in FY2025.',
               'The Q3 contemporaneous release is absent from the permitted sources.']:
   self.assertTrue(result_matches(text,node))
   self.assertTrue(validate_report('Q3 FY2024 gap: '+text+' [S4]',SOURCES,[],{'own_quarter_release':True})['passed'])

class RepairTests(unittest.TestCase):
 def test_default_runtime_rejects_faulty_table_and_accepts_repair(self):
  from test_runtime_integration import ToolFake,message
  from langchain_core.messages import AIMessage
  from runtime_adapter import assemble,agent_input,REPORT_PATH
  from phase1_request_policy import ReportRequest,required_headings
  from run_report import DEFAULT_BUDGET
  from provenance import digest
  async def check(fault):
   with tempfile.TemporaryDirectory() as directory:
    out=Path(directory);sources=[]
    for i,value in enumerate(['36.5','39.1','40.6','48.4'],1):
     text=f'Q{i} FY2024 revenue {value} billion.'
     sources.append(dict(source_kind='web',document_id=f'q{i}',title=f'Q{i} FY2024',fiscal_year=2024,fiscal_quarter=i,source_url=f'https://example.org/q{i}',retrieval_url=f'https://example.org/q{i}',text=text,text_sha256=digest(text.encode()),char_start=0,char_end=len(text),chunk_id=f'q{i}',evidence_id=f'q{i}'))
    packet=dict(source_mode='web_only',uploaded=[],web=sources,retrieval={'mode':'frozen'})
    req=ReportRequest(task="Calculate half-year revenues using each quarter's own release.",source_mode='web_only')
    f,m=labelled(['36.5','39.1','40.6','48.4']);r=calculate_metrics(f,m,SOURCES)
    for fact,source in zip(f,sources):fact['source_quote']=source['text']
    table=report_for(['36.5','39.1','40.6','48.4'],r)
    good='\n\n'.join('## '+h+'\n\n'+(table if h=='Key Findings' else 'Reported evidence [S1][S2][S3][S4].') for h in required_headings(req.structure))
    bad=(good.replace('| H1 revenue | 75.6','| H1 revenue | 75.5') if fault=='arithmetic' else
         good.replace('| Q2 FY2024 | 39.1 | [S2]','| Q2 FY2024 | 39.1 | [S3]') if fault=='source' else
         '\n'.join(l for l in good.splitlines() if not l.startswith('| H2 revenue')))
    fake=ToolFake(responses=[message('retrieve_web_documents',{},'r'),message('calculate_report_metrics',{'facts':f,'metrics':m},'c'),message('write_file',{'path':REPORT_PATH,'content':bad},'bad'),message('write_file',{'path':REPORT_PATH,'content':good},'good'),AIMessage(content='Report generated.')])
    runtime,evidence=assemble(out,req,None,[],[],None,DEFAULT_BUDGET,model=fake,frozen_evidence=packet)
    result=await runtime.arun(agent_input(req));await runtime.aclose()
    self.assertEqual(result.status,'succeeded',result.terminal)
    self.assertEqual((out/'raw_report.md').read_text(),good)
    self.assertEqual([x['passed'] for x in evidence.validation_checks],[False,True])
    self.assertTrue(any(e.data.get('action')=='structured_report_denied' for e in result.trajectory))
    self.assertIn('calculate_report_metrics',(out/'agent/agent.yaml').read_text())
  for fault in ['arithmetic','source','missing_metric']:
   with self.subTest(fault=fault):asyncio.run(check(fault))

if __name__=='__main__':unittest.main()
