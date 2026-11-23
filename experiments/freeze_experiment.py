"""Freeze immutable evidence, the 21+3 plan and explicit resource limits."""
import argparse
from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from provenance import write_json, digest, source_version, snapshot
from phase1_document_retrieval import load_documents
from phase1_report_pipeline import build_prompt_package
from phase1_request_policy import ReportRequest
from embedding_adapter import CachedEmbeddings
from run_report import DEFAULT_BUDGET
from experiments.run_experiments import preflight


def create(web_run):
    checks=preflight()
    tasks=json.loads((ROOT/'experiments/tasks.json').read_text())
    rubric=json.loads((ROOT/'experiments/rubric.json').read_text())
    web_run=Path(web_run)
    audit=json.loads((web_run/'audit.json').read_text())
    if not audit['automatic_passed'] or audit['body_cited_source_kinds']!=['web']:
        raise ValueError('Select an accepted real web-only development run')
    web=json.loads((web_run/'evidence_ledger.json').read_text())
    for s in web:
        if s['source_kind']!='web':raise ValueError('Web snapshot contains local evidence')
        # Dates are read from the captured official release body, never inferred
        # from a fiscal-year title or search ordering.
        match=re.search(r'February\s+(\d{1,2}),?\s+2025',s['text'])
        if not match:raise ValueError('Official release body lacks verifiable publication date')
        s.update(publication_date=f'2025-02-{int(match.group(1)):02d}',
                 publication_date_status='official_body_date_extracted', cutoff_eligibility='within_cutoff',
                 date_extraction_evidence=match.group(), excerpt_sha256=digest(s['text'].encode()))
        if s['publication_date']>tasks['cutoff']:raise ValueError('Source is after cutoff')
    out=ROOT/'artifacts/experiment_freezes'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out.mkdir(parents=True)
    write_json(out/'tasks.json',tasks);write_json(out/'rubric.json',rubric)
    provider=CachedEmbeddings(ROOT/'artifacts/cache/bge_m3.json',max_calls=20,max_input_chars=30000)
    by_id={t['id']:t for t in tasks['tasks']}
    packets={}; plan=[]
    for condition in tasks['conditions']:
        task=by_id[condition['task_id']]; mode=condition['source_mode']
        request={k:task[k] for k in ('task','structure','style','depth')};request['source_mode']=mode
        local=[];retrieval={'mode':'frozen_web'};corpus=[]
        if mode!='web_only':
            docs={d.document_id:d for d in load_documents(ROOT/'data/corpus/processed',task['document_ids'])}
            pkg=build_prompt_package(replace(ReportRequest(**request),source_mode='uploaded_only'),
                ROOT/'data/corpus/processed',document_ids=task['document_ids'],
                retrieval_queries=task['queries'],embedding_provider=provider)
            retrieval=pkg['retrieval']
            for s in pkg['sources']:
                d=docs[s['document_id']];text=d.text[s['char_start']:s['char_end']]
                local.append(dict(s,source_kind='uploaded',text=text,text_sha256=d.sha256,
                    file_sha256=d.file_sha256,excerpt_sha256=digest(text.encode()),
                    evidence_id=f"upload:{d.sha256}:{s['char_start']}:{s['char_end']}",
                    retrieval_url=f"upload://{d.document_id}/{d.sha256}/{s['char_start']}-{s['char_end']}"))
            corpus=[{'id':d.document_id,'file_sha256':d.file_sha256,
                     'normalized_text_sha256':d.sha256} for d in docs.values()]
        packet={'source_mode':mode,'uploaded':local,'web':web if mode!='uploaded_only' else [],
                'retrieval':retrieval,'corpus':corpus,'web_source_run':str(web_run) if mode!='uploaded_only' else None}
        packet_path=out/(condition['id']+'_evidence.json');write_json(packet_path,packet)
        packets[condition['id']]=(packet_path,digest(packet_path.read_bytes()))
        for repetition in condition['repetitions']:
            plan.append({'purpose':'formal','condition_id':condition['id'],'repetition':repetition,
                'expected_model':'Qwen3.8-27B',
                'request':request,'document_ids':task['document_ids'] if mode!='web_only' else [],
                'queries':task['queries'] if mode!='web_only' else [],
                'frozen_evidence_file':str(packet_path),'frozen_evidence_sha256':packets[condition['id']][1],
                'budget':{**DEFAULT_BUDGET,'cost_limit':0}})
    for pair in tasks['customization_pairs']:
        base=next(c for c in plan if c['condition_id']==pair['base_condition'] and c['repetition']==pair['base_repetition'])
        plan.append({**base,'condition_id':pair['id'],'repetition':1,'customization_pair':pair,
                     'request':{**base['request'],**pair['change']}})
    write_json(out/'run_plan.json',plan)
    authorization={'source':'user messages on 2026-10-20',
        'llm':'remote Qwen3.8 provider declared free by user',
        'embedding':'SiliconFlow embedding declared free by user; keep calls serial',
        'monetary_limit':0,'currency':'not_applicable_free_services',
        'formal_generations':24,'max_model_requests':192,'max_output_tokens':1152000,
        'input_utf8_bytes_per_request':60000,'per_run_timeout_seconds':480,
        'batch_elapsed_budget_seconds':11520,'batch_concurrency':1,
        'embedding_preparation_max_calls':20,'embedding_preparation_max_input_chars':30000,
        'automatic_revisions':0,'automatic_retries':0}
    write_json(out/'budget_authorization.json',authorization)
    import autoresearch_frontier_finance
    runtime_root=Path(autoresearch_frontier_finance.__file__).resolve().parents[2]
    write_json(out/'freeze_manifest.json',{'status':'prepared_not_finalized',
        'code_sha256':source_version(ROOT)['sha256'], 'runtime':snapshot(runtime_root,ROOT/'artifacts/versions/runtime'),
        'corpus_manifest_sha256':checks['corpus']['manifest_sha256'],
        'files':{p.name:digest(p.read_bytes()) for p in sorted(out.glob('*.json'))},
        'model':{'provider':'vllm','name':'Qwen3.8-27B','temperature':0.2,'max_tokens':6000,
                 'enable_thinking':False,'seed':None,'model_revision':'unavailable'},
        'input_mode':'immutable_evidence_replay','embedding_preparation_calls':provider.calls,
        'embedding_preparation_usage':provider.usage,'requires':['offline frozen-packet contract test','accepted real hybrid sample']} )
    print(out)
    return out


def finalize(path):
    path=Path(path);m=json.loads((path/'freeze_manifest.json').read_text())
    if source_version(ROOT)['sha256']!=m['code_sha256']:raise ValueError('Code changed; prepare a new freeze')
    for name,sha in m['files'].items():
        if digest((path/name).read_bytes())!=sha:raise ValueError('Frozen input changed: '+name)
    result=json.loads((ROOT/'artifacts/verification/offline_preflight.json').read_text())
    if not result['passed'] or result['code']['sha256']!=m['code_sha256']:
        raise ValueError('Run current offline preflight first')
    hybrid=[]
    for p in (ROOT/'artifacts/runs').glob('*/audit.json'):
        a=json.loads(p.read_text())
        if a.get('automatic_passed') and a.get('body_cited_source_kinds')==['uploaded','web']:
            hybrid.append(str(p.parent))
    if not hybrid:raise ValueError('No accepted real hybrid example')
    m.update(status='frozen',requires=[],hybrid_gate_evidence=hybrid,
             frozen_at=datetime.now(timezone.utc).isoformat(),
             code_snapshot=snapshot(ROOT,ROOT/'artifacts/versions/project'))
    write_json(path/'freeze_manifest.json',m)
    print(json.dumps({'freeze':str(path),'status':'frozen','sha256':digest((path/'freeze_manifest.json').read_bytes())}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--web-run',type=Path);p.add_argument('--finalize',type=Path)
    args=p.parse_args()
    if args.finalize:finalize(args.finalize)
    elif args.web_run:create(args.web_run)
    else:p.error('Use --web-run or --finalize')
