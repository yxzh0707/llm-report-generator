"""Three bounded live development probes through the existing enhanced worker."""
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from phase1_request_policy import ReportRequest
from runtime_adapter import ReportEvidenceMiddleware
from runtime_config import load_project_environment
from run_report import DEFAULT_BUDGET
from provenance import snapshot, write_json


async def main():
    load_project_environment()
    out = ROOT/'artifacts/financial_probes'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out.mkdir(parents=True)
    calls = [
        ('sec_filings', {'identifier': '1045810', 'form': '10-K', 'limit': 1}),
        ('tushare_query', {'api_name': 'trade_cal', 'params': {
            'exchange': 'SSE', 'start_date': '20250102', 'end_date': '20250102'},
            'fields': 'exchange,cal_date,is_open'}),
        ('alpha_vantage', {'function': 'GLOBAL_QUOTE', 'params': {'symbol': 'NVDA'}}),
    ]
    import autoresearch_frontier_finance
    runtime_root = Path(autoresearch_frontier_finance.__file__).resolve().parents[2]
    manifest = {'purpose': 'development_tool_probes', 'not_formal_experiment': True,
        'model_calls': 0, 'embedding_calls': 0, 'tool_call_limit': len(calls),
        'tool_timeout_seconds': 60, 'retries': 0, 'calls': calls,
        'code': snapshot(ROOT, ROOT/'artifacts/versions/project'),
        'runtime': snapshot(runtime_root, ROOT/'artifacts/versions/runtime'), 'results': []}
    write_json(out/'manifest.json', manifest)
    evidence = ReportEvidenceMiddleware(out, ReportRequest(task='Financial service probes', source_mode='web_only'),
        None, [], [], None, DEFAULT_BUDGET)
    context = SimpleNamespace(metadata={}, record=lambda *a, **k: None)
    for name, args in calls:
        started = time.monotonic()
        result = await evidence._call(name, args)
        evidence._record_scope(context, name, args, result)
        value = json.loads(result)
        write_json(out/(name+'.json'), value)
        manifest['results'].append({'tool': name, 'elapsed_seconds': time.monotonic()-started,
            'status': 'failed' if value.get('error') else 'returned',
            'error': value.get('error'), 'citation': value.get('citation'),
            'evidence_role': value.get('evidence_role')})
        write_json(out/'manifest.json', manifest)
    print(json.dumps({'output': str(out), 'results': manifest['results']}))


if __name__ == '__main__':
    asyncio.run(main())
