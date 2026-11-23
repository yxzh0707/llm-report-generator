"""Local report UI. Schedules one existing CLI process; does not own a model loop."""
from __future__ import annotations
import argparse
import base64
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import re
import secrets
import signal
import subprocess
import sys
import threading
import time
from urllib.parse import urlparse
import zipfile

from phase1_request_policy import ReportRequest
from provenance import digest, write_json
from runtime_config import load_project_environment, load_env_file, provider_settings
from run_report import DEFAULT_BUDGET

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = '20261020T103950535182Z'
MAX_BODY = 2_000_000
MAX_UPLOAD_BYTES = 1_000_000


def read_json(path, fallback=None):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return fallback


def read_text(path):
    try:
        return Path(path).read_text()
    except OSError:
        return ''


class RequestError(Exception):
    def __init__(self, message, status=400):
        self.status = status
        super().__init__(message)


class ReportApp:
    def __init__(self, root=ROOT, runner=None):
        self.root = Path(root)
        self.jobs = self.root/'artifacts/ui_jobs'
        self.jobs.mkdir(parents=True, exist_ok=True)
        self.token = secrets.token_urlsafe(32)
        self.lock = threading.Lock()
        self.active = None
        self.runner = runner or self.run_cli
        # A restarted server never silently resubmits a potentially paid job.
        for path in self.jobs.glob('*/job.json'):
            job = read_json(path, {})
            if job.get('status') in {'queued', 'running'}:
                job.update(status='interrupted', error='The server restarted. This task was not resubmitted automatically.')
                write_json(path, job)

    def documents(self):
        manifest = read_json(self.root/'data/corpus/processed/manifest.json', {})
        return [{k: doc[k] for k in ('id', 'title', 'source_url', 'chars') if k in doc}
                for doc in manifest.get('documents', [])]

    def bootstrap(self):
        try:
            settings = provider_settings()
            model_available = bool(os.getenv(settings['api_key_env']))
        except ValueError:
            model_available = False
        return {'token': self.token, 'documents': self.documents(),
            'services': {'model': model_available,
                'embedding': bool(os.getenv('SILICONFLOW_API_KEY'))},
            'budget': self.generation_budget(), 'active_job': self.active,
            'example_id': EXAMPLE if (self.root/'artifacts/runs'/EXAMPLE/'report.md').exists() else None}

    def generation_budget(self):
        budget = dict(DEFAULT_BUDGET)
        if os.getenv('DISSERTATION_PROVIDER') == 'tokenhub_openai':
            budget['cost_limit'] = None
        return budget

    def validate(self, payload):
        if not isinstance(payload, dict) or set(payload) - {'request', 'documents', 'uploads', 'submission_id'}:
            raise RequestError('Invalid request fields.')
        submission_id = payload.get('submission_id', '')
        if not isinstance(submission_id, str) or not re.fullmatch(r'[a-f0-9]{32}', submission_id):
            raise RequestError('Invalid submission ID. Refresh the page.')
        try:
            req = ReportRequest(**payload['request'])
            req.validate()
        except (ValueError, TypeError, KeyError, AttributeError):
            raise RequestError('Enter a task and choose valid sources, structure, style and depth.')
        if len(req.task) > 4000:
            raise RequestError('Task instructions must be at most 4,000 characters.')
        ids, uploads = payload.get('documents', []), payload.get('uploads', [])
        if not isinstance(ids, list) or not isinstance(uploads, list) or len(ids)+len(uploads) > 4:
            raise RequestError('Select up to 4 documents per report.')
        known = {d['id'] for d in self.documents()}
        if any(not isinstance(i, str) or i not in known for i in ids) or len(set(ids)) != len(ids):
            raise RequestError('Invalid example document selection.')
        if req.source_mode == 'web_only' and (ids or uploads):
            raise RequestError('Web-only mode cannot include uploaded documents.')
        if req.source_mode != 'web_only' and not (ids or uploads):
            raise RequestError('Select or upload at least one document.')
        decoded, total = [], 0
        for item in uploads:
            try:
                name = item['name']
                if not isinstance(name, str) or len(name) > 180 or '/' in name or '\\' in name:
                    raise ValueError()
                if Path(name).suffix.lower() not in {'.txt', '.md'}:
                    raise ValueError()
                data = base64.b64decode(item['data'], validate=True)
                text = data.decode('utf-8')
                if not text.strip() or '\x00' in text:
                    raise ValueError()
            except (KeyError, TypeError, ValueError, UnicodeError):
                raise RequestError('Uploads must be non-empty UTF-8 TXT or Markdown files.')
            total += len(data)
            if total > MAX_UPLOAD_BYTES:
                raise RequestError('Uploaded files must total no more than 1 MB.')
            decoded.append((name, data))
        return req, ids, decoded

    def submit(self, payload):
        req, ids, decoded = self.validate(payload)
        job_id = 'ui_'+payload['submission_id']
        payload_hash = digest(json.dumps(payload, sort_keys=True).encode())
        with self.lock:
            previous = read_json(self.jobs/job_id/'job.json')
            if previous:
                if previous['submission_sha256'] != payload_hash:
                    raise RequestError('A submission ID cannot be reused for a different task.', 409)
                return job_id
            if self.active:
                raise RequestError('A report is already running. Wait for it to finish before submitting.', 409)
            job_dir = self.jobs/job_id
            inputs = job_dir/'inputs'
            inputs.mkdir(parents=True)
            mappings = []
            for doc_id in ids:
                source = self.root/'data/corpus/processed'/(doc_id+'.md')
                if not source.is_file() or source.is_symlink():
                    raise RequestError('The example document is unavailable.')
                data = source.read_bytes()
                (inputs/source.name).write_bytes(data)
                mappings.append({'document_id': doc_id, 'original_name': source.name,
                                 'file_sha256': digest(data), 'origin': 'example_corpus'})
            for index, (name, data) in enumerate(decoded):
                identity = f'upload_{digest(data)[:16]}_{index+1}'
                (inputs/(identity+Path(name).suffix.lower())).write_bytes(data)
                ids = [*ids, identity]
                mappings.append({'document_id': identity, 'original_name': name,
                                 'file_sha256': digest(data), 'origin': 'user_upload'})
            from dataclasses import asdict
            config = {'purpose': 'development_ui', 'request': asdict(req),
                'corpus_root': str(inputs), 'document_ids': ids, 'queries': [req.task],
                'budget': self.generation_budget(), 'ui_input_mapping': mappings}
            # Save the executable budget before any provider call.
            write_json(job_dir/'config.json', config)
            job = {'id': job_id, 'title': req.task[:100], 'status': 'queued',
                'source_mode': req.source_mode, 'created_at': datetime.now(timezone.utc).isoformat(),
                'submission_sha256': payload_hash, 'input_mapping': mappings}
            write_json(job_dir/'job.json', job)
            self.active = job_id
            threading.Thread(target=self.execute, args=(job_id, config), daemon=True).start()
        return job_id

    def execute(self, job_id, config):
        path = self.jobs/job_id/'job.json'
        job = read_json(path)
        job.update(status='running')
        write_json(path, job)
        try:
            self.runner(job_id, config)
            manifest = read_json(self.root/'artifacts/runs'/job_id/'run_manifest.json', {})
            status = manifest.get('status')
            job.update(status='completed' if status == 'succeeded' else 'failed')
            if status != 'succeeded':
                job['error'] = 'Generation did not complete: '+str(manifest.get('error_code') or manifest.get('error_type') or status or 'Interrupted')
        except Exception as exc:
            job.update(status='failed', error='Report process failed: '+type(exc).__name__)
        finally:
            job['finished_at'] = datetime.now(timezone.utc).isoformat()
            write_json(path, job)
            with self.lock:
                self.active = None

    def run_cli(self, job_id, config):
        out = self.root/'artifacts/runs'/job_id
        with (self.jobs/job_id/'process.log').open('w') as log:
            proc = subprocess.Popen([sys.executable, str(self.root/'src/run_report.py'),
                '--config', str(self.jobs/job_id/'config.json'), '--output-dir', str(out)],
                cwd=self.root, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            try:
                proc.wait(timeout=DEFAULT_BUDGET['run_timeout_seconds']+90)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGTERM)
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait()
                raise

    def run_path(self, job_id):
        if job_id == EXAMPLE and (self.root/'artifacts/runs'/EXAMPLE).is_dir():
            return self.root/'artifacts/runs'/EXAMPLE
        if not re.fullmatch(r'ui_[a-f0-9]{32}', job_id) or not (self.jobs/job_id/'job.json').is_file():
            raise RequestError('Run not found.', 404)
        return self.root/'artifacts/runs'/job_id

    def history(self):
        jobs = [read_json(p, {}) for p in self.jobs.glob('*/job.json')]
        return sorted(jobs, key=lambda j: j.get('created_at', ''), reverse=True)[:30]

    def detail(self, job_id):
        out = self.run_path(job_id)
        manifest = read_json(out/'run_manifest.json', {})
        job = read_json(self.jobs/job_id/'job.json', {
            'id': job_id, 'title': 'NVIDIA balance-sheet briefing', 'status': 'completed', 'historical_example': True})
        events = []
        native = out/'native/execution/events.jsonl'
        event_path = native if native.exists() else out/'trajectory.jsonl'
        for line in read_text(event_path).splitlines():
            try:
                row = json.loads(line)
                kind, data = row.get('type'), row.get('data', {})
                if kind == 'tool_requested':
                    events.append({'type': kind, 'name': data.get('tool_call', {}).get('name', 'tool'),
                                   'at': row.get('timestamp')})
                elif kind in {'model_started', 'model_completed', 'tool_completed', 'tool_failed'}:
                    events.append({'type': kind, 'at': row.get('timestamp')})
            except ValueError:
                continue
        sources = read_json(out/'evidence_ledger.json', [])
        attempts = read_json(out/'provider_attempts.json', [])
        report = read_text(out/'report.md')
        return {'job': job, 'request': read_json(out/'request.json', {}),
            'report': report, 'sources': sources, 'audit': read_json(out/'audit.json', {}),
            'development_review': read_json(out/'assistant_development_review.json'),
            'events': events[-60:], 'model_attempts': len(attempts),
            'tools': read_json(out/'tool_inputs.json', []),
            'summary': {k: manifest[k] for k in ('status', 'usage', 'elapsed_seconds',
                'model_calls', 'embedding_calls', 'automatic_passed', 'error_code', 'error_type',
                'started_at') if k in manifest},
            'versions': {k: manifest.get(k, {}).get('sha256') for k in ('code', 'runtime')}}

    def download(self, job_id, kind):
        out = self.run_path(job_id)
        if kind in {'report', 'raw'}:
            path = out/('report.md' if kind == 'report' else 'raw_report.md')
            if not path.is_file() or not path.stat().st_size:
                raise RequestError('The report is not available yet.', 404)
            return path.read_bytes(), 'text/markdown; charset=utf-8', kind+'.md'
        if kind != 'bundle':
            raise RequestError('Invalid download type.', 404)
        if self.active == job_id:
            raise RequestError('Wait until the run finishes before downloading its bundle.', 409)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
            for base, prefix in ((out, 'run'), (self.jobs/job_id, 'submission')):
                for path in base.rglob('*'):
                    if path.is_file() and not path.is_symlink():
                        archive.write(path, prefix+'/'+str(path.relative_to(base)))
        return buffer.getvalue(), 'application/zip', job_id+'.zip'


def make_server(app, port=8767):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def send(self, status, data, content_type='application/json; charset=utf-8', filename=None):
            if not isinstance(data, bytes):
                data = json.dumps(data, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            if filename:
                self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
            self.end_headers()
            self.wfile.write(data)

        def local_request(self, mutation=False):
            hosts = {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}
            if self.headers.get('Host') not in hosts:
                raise RequestError('Only local access is supported.', 403)
            if mutation and (self.headers.get('X-Report-Token') != app.token or (
                self.headers.get('Origin') and self.headers['Origin'] not in {'http://'+h for h in hosts})):
                raise RequestError('Your page session has expired. Refresh and try again.', 403)

        def do_GET(self):
            try:
                self.local_request()
                path = urlparse(self.path).path
                static = {'/': ('index.html', 'text/html; charset=utf-8'),
                    '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                    '/styles.css': ('styles.css', 'text/css; charset=utf-8')}
                if path in static:
                    name, mime = static[path]
                    self.send(200, (app.root/'src/report_ui'/name).read_bytes(), mime)
                elif path == '/api/bootstrap':
                    self.send(200, app.bootstrap())
                elif path == '/api/jobs':
                    self.send(200, app.history())
                elif re.fullmatch(r'/api/jobs/[^/]+', path):
                    self.send(200, app.detail(path.split('/')[-1]))
                elif re.fullmatch(r'/api/jobs/[^/]+/download/[^/]+', path):
                    parts = path.split('/')
                    data, mime, filename = app.download(parts[3], parts[5])
                    self.send(200, data, mime, filename)
                else:
                    raise RequestError('Page not found.', 404)
            except RequestError as exc:
                self.send(exc.status, {'error': str(exc)})
            except (OSError, ValueError):
                self.send(500, {'error': 'Could not read the run record.'})

        def do_POST(self):
            try:
                self.local_request(mutation=True)
                if self.path != '/api/jobs':
                    raise RequestError('Endpoint not found.', 404)
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= MAX_BODY:
                    raise RequestError('The request must be no larger than 2 MB.', 413)
                if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                    raise RequestError('Only JSON requests are accepted.', 415)
                payload = json.loads(self.rfile.read(size))
                job_id = app.submit(payload)
                self.send(202, {'id': job_id})
            except RequestError as exc:
                self.send(exc.status, {'error': str(exc)})
            except (ValueError, UnicodeError):
                self.send(400, {'error': 'Invalid request format.'})
    return ThreadingHTTPServer(('127.0.0.1', port), Handler)


def main():
    import fcntl
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8767)
    args = parser.parse_args()
    lock_path = ROOT/'artifacts/ui_jobs/.server.lock'
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    server_lock = lock_path.open('a')
    try:
        fcntl.flock(server_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        parser.exit(1, 'A report UI server is already running.\n')
    load_project_environment()
    if os.getenv('DISSERTATION_EMBEDDING_ENV_FILE'):
        load_env_file(os.environ['DISSERTATION_EMBEDDING_ENV_FILE'])
    app = ReportApp()
    server = make_server(app, args.port)
    print(f'Report Studio: http://localhost:{server.server_port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        server_lock.close()


if __name__ == '__main__':
    main()
