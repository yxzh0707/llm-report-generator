import base64
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from report_server import ReportApp, RequestError, make_server
from provenance import write_json, source_version


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.calls = []
        self.release = threading.Event()
        def runner(job_id, config):
            self.calls.append(config)
            self.release.wait(3)
            out = self.root/'artifacts/runs'/job_id
            out.mkdir(parents=True)
            (out/'report.md').write_text('# Fixture report\n\nTest [S1]')
            (out/'raw_report.md').write_text('# Raw fixture')
            write_json(out/'run_manifest.json', {'status':'succeeded','usage':{'total_tokens':12}})
            write_json(out/'audit.json', {'automatic_passed':False})
            write_json(out/'evidence_ledger.json', [{'citation':'[S1]','text':'Fixture only'}])
        self.app = ReportApp(self.root, runner)
        self.server = make_server(self.app, 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = 'http://127.0.0.1:'+str(self.server.server_port)

    def tearDown(self):
        self.release.set()
        deadline = time.monotonic()+3
        while self.app.active and time.monotonic()<deadline:
            time.sleep(.01)
        self.server.shutdown();self.server.server_close();self.thread.join()
        self.tmp.cleanup()

    def payload(self, identity='a'*32):
        return {'submission_id':identity,'request':{'task':'Fixture task'},'documents':[],
            'uploads':[{'name':'notes.txt','data':base64.b64encode(b'Fixture evidence.').decode()}]}

    def post(self, payload, token=None, origin=None):
        headers={'Content-Type':'application/json','X-Report-Token':token or self.app.token}
        if origin:headers['Origin']=origin
        return urlopen(Request(self.url+'/api/jobs',json.dumps(payload).encode(),headers))

    def test_single_execution_idempotence_and_copied_upload_identity(self):
        payload=self.payload()
        payload['request'].update(min_words=250,max_words=500)
        with self.post(payload) as response:
            identity=json.load(response)['id']
        with self.post(payload) as response:
            self.assertEqual(json.load(response)['id'],identity)
        with self.assertRaises(HTTPError) as rejected:self.post(self.payload('b'*32))
        self.assertEqual(rejected.exception.code,409)
        self.release.set()
        deadline=time.monotonic()+3
        while self.app.active and time.monotonic()<deadline:time.sleep(.01)
        self.assertEqual(len(self.calls),1)
        config=self.calls[0]
        self.assertEqual(config['budget']['model_calls'],8)
        self.assertEqual(config['request']['min_words'],250)
        self.assertEqual(config['request']['max_words'],500)
        mapping=config['ui_input_mapping'][0]
        self.assertEqual(mapping['original_name'],'notes.txt')
        self.assertEqual((Path(config['corpus_root'])/(mapping['document_id']+'.txt')).read_bytes(),b'Fixture evidence.')
        detail=self.app.detail(identity)
        self.assertEqual(detail['job']['status'],'completed')
        self.assertFalse(detail['audit']['automatic_passed'])
        data,mime,_=self.app.download(identity,'bundle')
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            self.assertIn('run/report.md',archive.namelist())
            self.assertIn('submission/config.json',archive.namelist())

    def test_origin_host_and_token_rejected_without_execution(self):
        for kwargs in ({'token':'invalid'},{'origin':'https://untrusted.example'}):
            with self.assertRaises(HTTPError) as rejected:self.post(self.payload(),**kwargs)
            self.assertEqual(rejected.exception.code,403)
        with self.assertRaises(HTTPError) as rejected:
            urlopen(Request(self.url+'/api/bootstrap',headers={'Host':'untrusted.example'}))
        self.assertEqual(rejected.exception.code,403)
        self.assertEqual(self.calls,[])

    def test_input_source_closure_and_no_arbitrary_configuration(self):
        bad=[]
        value=self.payload();value['request']['source_mode']='web_only';bad.append(value)
        value=self.payload();value['uploads']=[];bad.append(value)
        value=self.payload();value['uploads'][0]['name']='../notes.txt';bad.append(value)
        value=self.payload();value['uploads'][0]['data']='not base64';bad.append(value)
        value=self.payload();value['budget']={'model_calls':999};bad.append(value)
        value=self.payload();value['documents']=['../../private'];bad.append(value)
        for value in bad:
            with self.assertRaises(RequestError):self.app.submit(value)
        self.assertEqual(list(self.app.jobs.glob('*/config.json')),[])
        with self.assertRaises(RequestError):self.app.detail('../../private')

    def test_setup_failure_is_persistent_and_not_completed(self):
        def fail(*args):raise RuntimeError('fixture failure with secret-like context')
        self.app.runner=fail
        identity=self.app.submit(self.payload())
        deadline=time.monotonic()+3
        while self.app.active and time.monotonic()<deadline:time.sleep(.01)
        detail=self.app.detail(identity)
        self.assertEqual(detail['job']['status'],'failed')
        self.assertEqual(detail['report'],'')
        self.assertNotIn('secret-like',detail['job']['error'])

    def test_ui_assets_are_in_source_archive_fingerprint(self):
        assets=self.root/'src/report_ui';assets.mkdir(parents=True)
        (assets/'app.js').write_text('const a=1;')
        (assets/'styles.css').write_text('body{}')
        (assets/'index.html').write_text('<html></html>')
        first=source_version(self.root)
        self.assertEqual(len(first['files']),3)
        (assets/'app.js').write_text('const a=2;')
        self.assertNotEqual(first['sha256'],source_version(self.root)['sha256'])
