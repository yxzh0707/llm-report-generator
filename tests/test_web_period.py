import asyncio,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from web_period import classify_release,inspect_web_source,validate_scope

class PeriodTests(unittest.TestCase):
 def test_primary_results_subheading_without_year_in_title(self):
  text='Issuer Reports Third Quarter Earnings\nQ3 FY 2025 Results:\nRevenue14.1b\nQ4 FY 2025 Guidance:\nRevenue15b'
  r=classify_release('https://example.com/news/2025/05',text)
  self.assertEqual((r['fiscal_year'],r['fiscal_quarter']),(2025,3))
 def test_release_verb_with_explicit_fiscal_earnings_title(self):
  r=classify_release('https://example.com/news/2024/11','Issuer Releases Q3 FY25 Earnings\nPublished November2024')
  self.assertEqual((r['fiscal_year'],r['fiscal_quarter']),(2025,3))
 def test_pdf_and_sec_fiscal_filename(self):
  for url,text,q in [('https://example.com/q3-fy25-earnings-release.pdf','--- Page 1 ---\nIssuer Reports\nThird Quarter Results\nPublished2024',3),
    ('https://example.com/Earnings+Release+(FY25+Q4).pdf','--- Page 1 ---\nIssuer reports\nfourth quarter results\nFY26 guidance',4),
    ('https://www.sec.gov/Archives/edgar/data/1/2/earningsreleasefy25q4.htm','EX-99.1\nIssuer reports fourth quarter results\nFY26 guidance',4)]:
   with self.subTest(url=url):
    r=classify_release(url,text);self.assertEqual((r['fiscal_year'],r['fiscal_quarter']),(2025,q))
 def test_fiscal_filename_cannot_override_conflicting_heading(self):
  for text in ['--- Page 1 ---\nIssuer Reports Fourth Quarter Results','--- Page 1 ---\nIssuer Reports Third Quarter 2024 Results']:
   self.assertEqual(classify_release('https://example.com/q3-fy25-earnings-release.pdf',text)['reason'],'conflicting_periods')
 def test_guidance_comparison_and_publication_dates_not_primary_periods(self):
  for lead in ['Q4 FY2025 Guidance: Revenue15b','Comparative periods: Q3 FY2024 and Q3 FY2025','Published May14,2025']:
   r=classify_release('https://example.com/news/2025/05','Issuer Reports Third Quarter Earnings\n'+lead)
   self.assertEqual(r['status'],'unverified')
 def test_results_subheading_must_agree_with_current_heading(self):
  r=classify_release('https://example.com','Issuer Reports Third Quarter Earnings\nQ4 FY2025 Results:\nRevenue5b')
  self.assertEqual(r['reason'],'conflicting_periods')
 def test_filename_does_not_turn_transcript_into_release(self):
  self.assertEqual(classify_release('https://example.com/q3-fy25.pdf','Third Quarter Earnings Call\nQ3 FY2025 Results: Revenue5b')['status'],'not_release')
 def test_fiscal_year_is_not_publication_year(self):
  r=classify_release('https://example.com/releases/2025/january','Issuer Reports Fourth-Quarter and Full-Year 2024 Financial Results\nPublished January2025')
  self.assertEqual((r['fiscal_year'],r['fiscal_quarter']),(2024,4))
 def test_current_release_not_comparative_year(self):
  text='Issuer Reports Third Quarter 2025 Financial Results\nRevenue 180b vs158b in third quarter 2024.'
  r=inspect_web_source({'source_url':'https://example.com'},text,{'fiscal_year':2024})
  self.assertEqual(r['decision'],'exclude')
 def test_calendar_issuer_primary_end_requires_declaration(self):
  text='Issuer Announces Third Quarter Results\nIssuer today announced financial results for its third quarter ended September 30, 2024.'
  self.assertEqual(classify_release('https://example.com/2025',text)['status'],'unverified')
  r=classify_release('https://example.com/2025',text,calendar_fiscal_year=True)
  self.assertEqual(r['fiscal_year'],2024)
 def test_fiscal_lead_not_calendar_quarter(self):
  text='Issuer reports first quarter results\nIssuer today announced financial results for its fiscal 2025 first quarter ended December28,2024.'
  r=classify_release('https://example.com/2025/01',text)
  self.assertEqual((r['fiscal_year'],r['fiscal_quarter']),(2025,1))
 def test_nonrelease_and_unknown_pages_quarantined(self):
  for text in ['Issuer to Report Third-Quarter 2024 Financial Results','Investor Relations\nIssuer Reports Third Quarter 2024 Results','2024 Q3 Earnings Call','Issuer reports third quarter results\nPublished 2024-10-01']:
   self.assertEqual(inspect_web_source({'source_url':'https://example.com'},text,{'fiscal_year':2024})['decision'],'quarantine')
 def test_conflicting_heading_and_fiscal_path_not_guessed(self):
  r=classify_release('https://example.com/fy-2024-q3/press-release','FY25 Q3 - Press Releases')
  self.assertEqual(r['reason'],'conflicting_periods')
 def test_pdf_and_supporting_statement_roles(self):
  r=classify_release('https://example.com/a.pdf','--- Page 1 ---\nIssuer Announces Financial Results for Fourth Quarter\nand Fiscal 2025\nRevenue35b')
  self.assertEqual(r['fiscal_year'],2025)
  self.assertEqual(classify_release('https://example.com/fy-2024-q3/metrics','FY24 Q3 - Metrics')['status'],'not_release')
 def test_invalid_scope_and_quarter_exclusion(self):
  with self.assertRaises(ValueError):validate_scope({'fiscal_year':'2024'})
  r=inspect_web_source({'source_url':'https://example.com'},'Issuer Reports First Quarter 2024 Results',{'fiscal_year':2024,'quarters':[3,4]})
  self.assertEqual(r['reason'],'wrong_fiscal_quarter')
 def test_live_and_frozen_paths_share_admission(self):
  from runtime_adapter import ReportEvidenceMiddleware
  from phase1_request_policy import ReportRequest
  from run_report import DEFAULT_BUDGET
  from provenance import digest
  texts=['Issuer Reports Third Quarter 2024 Results\nRevenue5b','Issuer Reports Third Quarter 2025 Results\nRevenue6b','Investor Relations\nFinancial results']
  async def run():
   for mode in ['off','enforce']:
    with tempfile.TemporaryDirectory() as folder:
     out=Path(folder);sources=[];replay={}
     for i,text in enumerate(texts):
      url=f'https://example.com/source{i}';s=dict(source_kind='web',document_id=str(i),title=url,source_url=url,retrieval_url=url,text=text,text_sha256=digest(text.encode()),char_start=0,char_end=len(text),chunk_id=str(i),evidence_id=str(i))
      sources.append(s);replay[json.dumps({'name':'web_fetch','arguments':{'url':url}},sort_keys=True)]={'url':url,'text':text}
     scope={'fiscal_year':2024};req=ReportRequest(task='FY2024 report',source_mode='web_only')
     live=ReportEvidenceMiddleware(out,req,None,[],[],None,DEFAULT_BUDGET,web_replay=replay,web_period_scope=scope,web_period_filter=mode)
     for i in range(3):await live._call('web_fetch',{'url':f'https://example.com/source{i}'})
     frozen=ReportEvidenceMiddleware(out,req,None,[],[],None,DEFAULT_BUDGET,frozen_evidence={'web':sources,'uploaded':[]},web_period_scope=scope,web_period_filter=mode)
     await frozen._call('retrieve_web_documents',{})
     self.assertEqual(len(live.sources),3 if mode=='off' else 1)
     self.assertEqual([s['source_url'] for s in live.sources],[s['source_url'] for s in frozen.sources])
     self.assertEqual(live.sources[0]['fiscal_year'],2024)
  asyncio.run(run())

if __name__=='__main__':unittest.main()
