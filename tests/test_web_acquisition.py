import asyncio,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import AsyncMock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from web_acquisition import useful_links,grant_observed_links,retryable
from web_period import classify_release

class AcquisitionTests(unittest.TestCase):
 def test_link_ranking_bounded_public_url_and_discovery_only(self):
  links=[{'url':'https://cdn.example.com/a.pdf','title':'Earnings release'},
         {'url':'https://user:password@example.com/a.pdf','title':'Secret'},
         {'url':'javascript:alert(1)','title':'Earnings'},
         {'url':'https://example.com/privacy','title':'Privacy'}]
  r=useful_links({'links':links+links},1)
  self.assertEqual(len(r),1);self.assertEqual(r[0]['url'],links[0]['url']);self.assertEqual(r[0]['evidence_role'],'discovery_only')
 def test_grants_preserve_search_hosts_and_worker_blocks_private_addresses(self):
  from autoresearch_frontier_finance._vendor.fflow.tools import _public_url
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'grants.json';p.write_text('["sec.gov"]');grant_observed_links(p,[{'url':'https://cdn.example.com/a.pdf'}])
   self.assertEqual(json.loads(p.read_text()),['cdn.example.com','sec.gov'])
   with self.assertRaises(ValueError):_public_url('http://127.0.0.1/earnings.pdf')
 def test_no_retry_on_access_denial(self):
  self.assertFalse(retryable({'error':'HTTP403 Forbidden'}));self.assertTrue(retryable({'error':'HTTP503 Service Unavailable'}))
 def test_release_pdf_precedes_transcript(self):
  r=useful_links({'links':[{'url':'https://example.com/earnings-transcript.pdf','title':'Transcript'},{'url':'https://example.com/earnings-release.pdf','title':'Release'}]})
  self.assertIn('earnings-release.pdf',r[0]['url'])
 def test_sec_heading_and_fiscal_year_before_quarter(self):
  r=classify_release('https://www.sec.gov/Archives/edgar/data/1/x.htm','Exhibit99.1\nIssuer Announces Third Quarter 2024 Results\nRevenue5b')
  self.assertEqual((r['fiscal_year'],r['fiscal_quarter']),(2024,3))
  r=classify_release('https://example.com/release','Issuer Announces Fiscal 2025 Third Quarter Financial Results\nRevenue5b')
  self.assertEqual((r['fiscal_year'],r['fiscal_quarter']),(2025,3))
 def test_invalid_json_retries_once_and_retains_all_attempts(self):
  from runtime_adapter import ReportEvidenceMiddleware
  from autoresearch_frontier_finance.runtime_adapter import FFlowMiddleware
  from phase1_request_policy import ReportRequest
  from run_report import DEFAULT_BUDGET
  async def check():
   with tempfile.TemporaryDirectory() as d:
    m=ReportEvidenceMiddleware(Path(d),ReportRequest(task='Research',source_mode='web_only'),None,[],[],None,DEFAULT_BUDGET,web_acquisition='bounded')
    self.assertEqual(m.env['FFLOW_ATTACHMENT_LINKS'],'1')
    mock=AsyncMock(side_effect=['{broken',json.dumps({'text':'opened','url':'https://example.com'})])
    with patch.object(FFlowMiddleware,'_call',mock):r=await m.bounded_network_call('web_fetch',{'url':'https://example.com'})
    self.assertEqual(r['text'],'opened');self.assertEqual(mock.await_count,2);self.assertEqual(len(m.network_attempts),2)
    with patch.object(FFlowMiddleware,'_call',AsyncMock(return_value='{broken')) as mock:
     r=await m.bounded_network_call('web_fetch',{'url':'https://example.com'})
     self.assertEqual(mock.await_count,2);self.assertIn('Invalid JSON',r['error'])
  asyncio.run(check())
 def test_upload_subset_keeps_live_network_tools(self):
  from runtime_adapter import ReportEvidenceMiddleware
  from phase1_request_policy import ReportRequest
  from run_report import DEFAULT_BUDGET
  async def check():
   with tempfile.TemporaryDirectory() as d:
    m=ReportEvidenceMiddleware(Path(d),ReportRequest(task='Report',source_mode='hybrid'),None,[],[],None,DEFAULT_BUDGET,uploaded_evidence={'uploaded':[],'web':[]})
    self.assertIn('web_search',m.names);self.assertIn('web_fetch',m.names);self.assertNotIn('retrieve_web_documents',m.names)
    r=json.loads(await m._call('retrieve_uploaded_documents',{}));self.assertEqual(r['sources'],[])
  asyncio.run(check())

if __name__=='__main__':unittest.main()
