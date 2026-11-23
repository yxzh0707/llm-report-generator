"""Offline gates, budget preparation and artifact-only result reconstruction.

This entry point never launches a paid batch. Formal execution is gated on a
reviewable freeze receipt, approved budget and validated web/evidence replay.
"""
import argparse
import csv
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from provenance import source_version, write_json, digest, environment
from corpus_check import verify
from run_report import DEFAULT_BUDGET


def preflight():
    tasks = json.loads((ROOT/'experiments/tasks.json').read_text())
    rubric = json.loads((ROOT/'experiments/rubric.json').read_text())
    assert len(tasks['tasks']) == 6
    assert sum(len(c['repetitions']) for c in tasks['conditions']) == 21
    assert len(tasks['customization_pairs']) == 3
    by_id = {t['id']: t for t in tasks['tasks']}
    assert by_id['T5']['task'] == by_id['T6']['task']
    assert len(rubric['human_source_audit']['preselected']) >= 4
    assert rubric['human_source_audit']['claims_per_report'] == 5
    for pair in tasks['customization_pairs']:
        assert len(pair['change']) == 1
    corpus = verify(ROOT/'data/corpus/processed')
    return {'passed': True, 'main_generations': 21, 'paired_generations': 3,
            'corpus': corpus, 'tasks_sha256': digest((ROOT/'experiments/tasks.json').read_bytes()),
            'rubric_sha256': digest((ROOT/'experiments/rubric.json').read_bytes()),
            'code': source_version(ROOT), 'environment': environment()}


def prepare():
    result = preflight()
    b = DEFAULT_BUDGET
    bound = 24*b['model_calls']
    result.update(status='not_frozen_pending_gates', model_parameters={
        'provider': 'vllm', 'model': 'Qwen3.8-27B', 'model_revision': 'unavailable',
        'temperature': 0.2, 'max_tokens': b['output_tokens_per_call'], 'enable_thinking': False,
        'seed': None, 'stream_usage': True}, budget={
        'per_run': b, 'max_model_requests': bound,
        'max_output_tokens': bound*b['output_tokens_per_call'],
        'conservative_total_token_estimate': bound*(b['prompt_utf8_bytes_per_call']+b['output_tokens_per_call']+512),
        'token_estimate_method': 'serialized input UTF-8 byte cap + output token cap + 512 framing allowance; not provider tokenizer measurement',
        'max_sequential_run_seconds': 24*b['run_timeout_seconds'],
        'max_tool_calls': 24*b['tool_calls'], 'max_web_search_calls': 6*b['web_search_calls'],
        'cost_currency': 'not_applicable_free_services', 'cost_limit': 0,
        'cost_estimate': 0, 'cost_basis':'User confirmed Qwen3.8 and SiliconFlow embedding free on 2026-10-20; usage/time still capped'},
        retrieval={'version':'sentence-parent-child-v1','child_target_max':[1000,1500],
            'parent_target_max':[2400,4000],'parent_context_chars':18000,'top_k':8,
            'queries':'frozen in tasks.json; round-robin dedup children, expand unique parents',
            'embedding':'BAAI/bge-m3, 1024 dimensions, actual-text cache',
            'web_search_num':3,'web_excerpt_max_chars':6000},
        unresolved_gates=['final immutable web/evidence packets and same-evidence customization receipt',
            'final code/prompt/dependency snapshots after development fixes',
            'G3 real web_only/hybrid smoke acceptance'],
        freeze_rule='Do not call this a formal freeze until unresolved gates are removed with evidence.')
    observed = []
    for path in sorted((ROOT/'artifacts/runs').glob('*/run_manifest.json')):
        m = json.loads(path.read_text())
        if m.get('purpose') == 'development_integration' and (m.get('usage') or {}).get('total_tokens') is not None:
            observed.append({'run_id': m['run_id'], 'status':m['status'], 'tokens':m['usage']['total_tokens'],
                             'elapsed_seconds':m['elapsed_seconds']})
    result['pilot_observations'] = observed
    return result


def summarize():
    rows=[]
    for p in sorted((ROOT/'artifacts/runs').glob('*/run_manifest.json')):
        m=json.loads(p.read_text());a=json.loads((p.parent/'audit.json').read_text()) if (p.parent/'audit.json').exists() else {}
        rows.append({'run_id': m['run_id'], 'purpose': m.get('purpose'),
            'generation_stage':m.get('generation_stage'), 'retry_of':m.get('retry_of'),
            'source_mode':m.get('request',{}).get('source_mode'), 'runtime_status':m.get('status'),
            'automatic_passed':m.get('automatic_passed',False),'human_review_completed':False,
            'strict_success':False if not m.get('automatic_passed') else None,
            'model_calls':m.get('model_calls'), 'tool_calls':m.get('tool_calls'),
            'total_tokens':(m.get('usage') or {}).get('total_tokens'),
            'elapsed_seconds':m.get('elapsed_seconds'), 'error_code':m.get('error_code'),
            'code_sha256':m.get('code',{}).get('sha256'), 'corpus_sha256':m.get('corpus_sha256')})
    out=ROOT/'artifacts/tables';out.mkdir(parents=True,exist_ok=True)
    write_json(out/'runs.json',rows)
    if rows:
        with (out/'runs.csv').open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    lines=['# Development and formal runs (separate by purpose)', '',
           '| run_id | purpose | mode | runtime | automatic | tokens | failure |',
           '|---|---|---|---|---|---|---|']
    lines += [f"| {r['run_id']} | {r['purpose']} | {r['source_mode']} | {r['runtime_status']} | {r['automatic_passed']} | {r['total_tokens'] if r['total_tokens'] is not None else 'unknown'} | {r['error_code'] or ''} |" for r in rows]
    (out/'runs.md').write_text('\n'.join(lines)+'\n')
    return {'runs':len(rows),'formal_runs':sum(r['purpose']=='formal' for r in rows),
            'failed_runtime_runs':sum(r['runtime_status']!='succeeded' for r in rows),
            'human_audit_completed':False,'tables':str(out)}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['offline','prepare','summarize'], required=True)
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    out=ROOT/'artifacts/verification';out.mkdir(parents=True,exist_ok=True)
    if args.mode=='offline':
        result=preflight()
        if args.check:
            completed=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-v'],cwd=ROOT,
                                     stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
            (out/'unittest-runtime.log').write_text(completed.stdout)
            if completed.returncode:
                raise SystemExit(completed.stdout)
            result['tests']='unittest-runtime.log: passed'
        write_json(out/'offline_preflight.json',result)
    elif args.mode=='prepare':
        result=prepare();write_json(out/'experiment_preparation.json',result)
    else:
        result=summarize()
    print(json.dumps({k:v for k,v in result.items() if k not in {'code','corpus','environment'}},indent=2))


if __name__=='__main__':
    main()
