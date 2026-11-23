import asyncio,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from evidence_workspace import EvidenceWorkspace
from provenance import digest

class WorkspaceTests(unittest.TestCase):
 def test_exact_unicode_offsets_and_case_whitespace_search(self):
  with tempfile.TemporaryDirectory() as d:
   w=EvidenceWorkspace(d);text='汉字'*4000+'Three\n Months Ended February 28, 2025'+' more'*1000
   doc=w.archive({'source_url':'https://example.org/report'},text,upstream_truncated=True)
   x,parent,spans,n=w.access('search_evidence',{'document_id':doc['document_id'],'query':'three months ended'})
   self.assertEqual(len(spans),1);a,b,t=spans[0];self.assertEqual(t,text[a:b]);self.assertIn('February 28, 2025',t);self.assertTrue(x['upstream_truncated'])
   x,p,spans,n=w.access('read_evidence',{'document_id':doc['document_id'],'start':7990,'length':100})
   self.assertEqual(spans[0],(7990,8090,text[7990:8090]))
 def test_no_arbitrary_paths_unknown_documents_invalid_offsets_or_regex(self):
  with tempfile.TemporaryDirectory() as d:
   w=EvidenceWorkspace(d);doc=w.archive({'source_url':'https://example.org'},'abcd'*2000,upstream_truncated=False);key=doc['document_id']
   for args in [{'document_id':'../../secret','start':0},{'document_id':key,'start':-1},{'document_id':key,'start':True},{'document_id':key,'start':0,'length':6001},{'document_id':key,'start':0,'path':'x'}]:
    with self.assertRaises(ValueError):w.access('read_evidence',args)
   self.assertEqual(w.access('search_evidence',{'document_id':key,'query':'.*'})[2],[])
   (w.root/(key+'.txt')).write_text('tampered')
   with self.assertRaisesRegex(ValueError,'integrity'):w.access('read_evidence',{'document_id':key,'start':0})
 def test_pagination_is_bounded_and_does_not_drop_later_matches(self):
  with tempfile.TemporaryDirectory() as d:
   w=EvidenceWorkspace(d);text=('needle'+'x'*3000)*7;doc=w.archive({'source_url':'https://example.org'},text,upstream_truncated=False)
   start=0;seen=[]
   while True:
    _,_,spans,n=w.access('search_evidence',{'document_id':doc['document_id'],'query':'needle','start':start})
    self.assertLessEqual(sum(b-a for a,b,t in spans),6000);seen+=spans
    if n is None:break
    self.assertGreater(n,start);start=n
   self.assertEqual(len(seen),7)
 def test_adapter_archive_read_provenance_and_off_arm(self):
  from runtime_adapter import ReportEvidenceMiddleware,tool_names
  from phase1_request_policy import ReportRequest
  from run_report import DEFAULT_BUDGET
  async def check():
   text='prefix '*1000+'Three Months Ended February 28, 2025'+' tail'*1000;url='https://example.org/release'
   replay={json.dumps({'name':'web_fetch','arguments':{'url':url}},sort_keys=True):{'url':url,'text':text,'truncated':True}}
   for mode in ['off','on']:
    with tempfile.TemporaryDirectory() as d:
     m=ReportEvidenceMiddleware(Path(d),ReportRequest(task='Report',source_mode='web_only'),None,[],[],None,DEFAULT_BUDGET,web_replay=replay,evidence_workspace=mode)
     r=json.loads(await m._call('web_fetch',{'url':url}));self.assertEqual(r['text'],text[:6000]);self.assertEqual('search_evidence' in m.names,mode=='on')
     if mode=='on':
      r=json.loads(await m._call('search_evidence',{'document_id':r['workspace_document_id'],'query':'Three Months Ended'}))
      s=r['excerpts'][0];self.assertIn('February 28, 2025',s['text']);self.assertEqual(s['text'],text[s['char_start']:s['char_end']]);self.assertEqual(s['excerpt_sha256'],digest(s['text'].encode()));self.assertEqual(s['source_url'],url);self.assertEqual(s['citation'],'[S2]');self.assertEqual(len(m.tool_log),2)
     else:self.assertFalse((Path(d)/'evidence_workspace').exists())
   self.assertNotIn('read_evidence',tool_names('uploaded_only',evidence_workspace='on'))
   self.assertNotIn('read_evidence',tool_names('web_only',frozen=True,evidence_workspace='on'))
  asyncio.run(check())
if __name__=='__main__':unittest.main()
