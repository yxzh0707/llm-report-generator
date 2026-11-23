import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from quote_binding import validate_quote_bindings,validate_quote_config
LABELS=['Q3 period end']
TEXT='Three Months Ended\nFebruary 28, 2025'
def report(value='2025-02-28',quote='Three Months Ended February 28, 2025',cite='[S2]'):
 return f'| Item | Date | Evidence |\n|---|---|---|\n| Q3 period end | {value} | "{quote}" {cite} |'
SOURCES=[{'citation':'[S1]','text':'Initial prefix with no period end.'},{'citation':'[S2]','text':TEXT}]
class QuoteBindingTests(unittest.TestCase):
 def test_whitespace_and_smart_quote_delimiters(self):
  self.assertTrue(validate_quote_bindings(report(),SOURCES,LABELS)['passed'])
  self.assertTrue(validate_quote_bindings(report().replace('"Three','“Three').replace('2025"','2025”'),SOURCES,LABELS)['passed'])
 def test_wrong_excerpt_returns_only_read_candidate(self):
  x=validate_quote_bindings(report(cite='[S1]'),SOURCES,LABELS)
  self.assertFalse(x['passed']);self.assertEqual(x['issues'][0]['candidate_citations'],['[S2]'])
 def test_fabricated_quote_and_invented_ellipsis_rejected(self):
  for quote in ['Three Months Ended January 31, 2025','Three Months Ended ... February 28, 2025']:
   x=validate_quote_bindings(report(quote=quote),SOURCES,LABELS);self.assertFalse(x['passed']);self.assertEqual(x['issues'][0]['candidate_citations'],[])
 def test_missing_omitted_duplicate_and_missing_citation(self):
  for text in ['no table',report()+'\n'+report(),report(cite=''),report().replace('"Three Months Ended February 28, 2025"',''),report().replace('| "Three Months Ended February 28, 2025" [S2]','')]:
   self.assertFalse(validate_quote_bindings(text,SOURCES,LABELS)['passed'])
 def test_unavailable_is_not_certified_support(self):
  x=validate_quote_bindings(report(value='Unavailable',quote=''),SOURCES,LABELS)
  self.assertTrue(x['passed']);self.assertEqual(x['checks'][0]['status'],'abstained');self.assertFalse(x['checks'][0]['quote_identity_verified'])
  self.assertFalse(validate_quote_bindings(report(value='2025-02-28 Unavailable',quote=''),SOURCES,LABELS)['passed'])
 def test_does_not_claim_value_truth_or_entailment(self):
  x=validate_quote_bindings(report(value='2025-01-31'),SOURCES,LABELS)
  self.assertTrue(x['passed']);self.assertFalse(x['checks'][0]['factual_entailment_verified'])
 def test_configuration_scope_and_no_unrequested_prose_checks(self):
  self.assertTrue(validate_quote_bindings('Wrong uncited prose',SOURCES,[])['passed'])
  for labels,mode in [([], 'enforce'),(['A','a'],'enforce'),('A','enforce'),(['A'],'bad')]:
   with self.assertRaises(ValueError):validate_quote_config(labels,mode)
 def test_adapter_audit_vs_enforcement(self):
  from runtime_adapter import ReportEvidenceMiddleware
  from phase1_request_policy import ReportRequest
  from run_report import DEFAULT_BUDGET
  for mode in ['off','enforce']:
   with tempfile.TemporaryDirectory() as d:
    m=ReportEvidenceMiddleware(Path(d),ReportRequest(task='Report',source_mode='web_only'),None,[],[],None,DEFAULT_BUDGET,calculation_control='off',report_validation='off',quote_binding=mode,quote_rows=LABELS)
    m.sources=SOURCES
    x=m.validate_candidate(report(cite='[S1]'));self.assertEqual(x['passed'],mode=='off');self.assertFalse(x['quote_binding']['passed']);self.assertTrue((Path(d)/'validation_checks.json').exists())
if __name__=='__main__':unittest.main()
