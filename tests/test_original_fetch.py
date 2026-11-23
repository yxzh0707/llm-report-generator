import asyncio,io,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from original_fetch import persist_extract,verified_original,download

class OriginalTests(unittest.TestCase):
 def test_html_original_and_fulltext_preserved_without_context_truncation(self):
  with tempfile.TemporaryDirectory() as d:
   data=b'<html><p>'+b'word '*8000+b'</p><p>Late evidence 987654</p></html>'
   r=persist_extract(data,'https://example.org',Path(d)/'raw','text/html')
   self.assertGreater(len(r['text']),30000);self.assertIn('Late evidence',r['text']);self.assertFalse(r['truncated'])
   public=verified_original(r,d);self.assertTrue(public['complete_extraction'])
   self.assertEqual(Path(r['original_archive']['raw_file']).read_bytes(),data)
 def test_tamper_or_external_path_is_not_admitted(self):
  with tempfile.TemporaryDirectory() as d,tempfile.TemporaryDirectory() as outside:
   r=persist_extract(b'text','https://example.org',Path(d)/'raw','text/plain')
   r['text']='changed'
   with self.assertRaisesRegex(ValueError,'mismatch'):verified_original(r,d)
   r=persist_extract(b'text','https://example.org',Path(outside)/'raw','text/plain')
   with self.assertRaisesRegex(ValueError,'within'):verified_original(r,d)
 def test_blank_pdf_is_partial_not_complete_and_text_caps_explicit(self):
  from pypdf import PdfWriter
  with tempfile.TemporaryDirectory() as d:
   w=PdfWriter();w.add_blank_page(width=100,height=100);b=io.BytesIO();w.write(b)
   r=persist_extract(b.getvalue(),'https://example.org',Path(d)/'pdf')
   self.assertTrue(r['truncated']);self.assertEqual(r['original_archive']['failed_pages'],[1])
   with patch('original_fetch.MAX_CHARS',10):r=persist_extract(b'x'*20,'https://example.org',Path(d)/'text','text/plain')
   self.assertEqual(len(r['text']),10);self.assertTrue(r['truncated'])
 def test_adapter_fulloriginal_reads_beyond_worker_limit_with_same_initial_prefix(self):
  from runtime_adapter import ReportEvidenceMiddleware,tool_names
  from phase1_request_policy import ReportRequest
  from run_report import DEFAULT_BUDGET
  async def check():
   for mode in ['off','on','full_original']:
    with tempfile.TemporaryDirectory() as d:
     out=Path(d);url='https://example.org/report';full=persist_extract(('prefix '*5000+'Balance sheet cash 12345').encode(),url,out/'source_originals','text/plain')
     v=full if mode=='full_original' else dict(url=url,text=full['text'][:30000],truncated=True)
     replay={json.dumps(dict(name='web_fetch',arguments={'url':url}),sort_keys=True):v}
     m=ReportEvidenceMiddleware(out,ReportRequest(task='Summarise',source_mode='web_only'),None,[],[],None,DEFAULT_BUDGET,web_replay=replay,evidence_workspace=mode)
     r=json.loads(await m._call('web_fetch',{'url':url}));self.assertEqual(r['text'],full['text'][:6000]);self.assertNotIn('original_archive',r)
     if mode!='off':
      s=json.loads(await m._call('search_evidence',{'document_id':r['workspace_document_id'],'query':'cash'}))
      self.assertEqual(bool(s['excerpts']),mode=='full_original')
      if mode=='full_original':self.assertEqual(s['document']['archive_scope'],'persisted_original_extracted_text')
   self.assertNotIn('read_evidence',tool_names('uploaded_only',evidence_workspace='full_original'))
   self.assertNotIn('read_evidence',tool_names('web_only',frozen=True,evidence_workspace='full_original'))
  asyncio.run(check())
 def test_fulloriginal_requires_bytes_provenance_and_forbidden_url_rejected(self):
  with self.assertRaises(ValueError):verified_original({'text':'forged'},'.')
  with tempfile.TemporaryDirectory() as d:
   for url in ['file:///etc/passwd','http://127.0.0.1/x']:
    with self.assertRaises(ValueError):download(url,d)

if __name__=='__main__':unittest.main()
