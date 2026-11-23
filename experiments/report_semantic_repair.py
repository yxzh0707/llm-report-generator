"""Development replay: four known prose defects; twelve unchanged gate controls.

No fresh generation comparison, task selection after outcomes or pooled main score.
"""
import argparse,asyncio,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'src'),str(ROOT/'analysis')]
from experiments.system_comparison import read,save,sha,now,BUDGET
from provenance import source_version,snapshot
from report_semantics import validate_narrative
P=ROOT/'artifacts/report_study/semantic_repair_11'
OLD=ROOT/'artifacts/report_study/system_optimization_10'
CASES={
 'broadcom_qualcomm_detailed':'narrative_growth_basis',
 'costco_target_missing':'narrative_period_overlap',
 'costco_target_standard':'narrative_ratio',
 'ibm_netflix_standard':'narrative_metric_label',
}

def prepare():
    P.mkdir(parents=True,exist_ok=False)
    save(P/'tasks.json',read(OLD/'tasks.json'))
    jobs=[dict(task_id=t,run_id=t+'_report_system_1',arm='report_system',repeat=1,expected_code=c) for t,c in CASES.items()]
    save(P/'jobs.json',jobs)
    save(P/'protocol.json',dict(created_utc=now(),type='known-failure development repair replay',
        model='Qwen3.8-27B',budget=BUDGET,repair_cases=CASES,
        unchanged_controls='All other twelve system_optimization_10 reports; deterministic full-save validation, no regeneration.',
        acceptance='Original four errors detected; Qwen saves a corrected complete report through the same gate; external numeric/format checks and source reading. Preserve all attempts.',
        context='Original task/draft and previously admitted full sources/calculations; no external answer key supplied to generator.',
        attempts='One bounded replay per case, no restart or best-of selection.',
        scope='Development regression only; not new held-out tasks and not a new Hermes comparison. Original batches immutable.'))
    paths=[OLD/'tasks.json']
    for t in read(P/'tasks.json'):
        folder=OLD/'runs'/(t['id']+'_report_system_1')
        paths.extend(folder/n for n in ['evaluated_report.md','evidence_ledger.json','calculation_calls.json','request.json','agent_input.json'])
        if (folder/'period_calls.json').exists():paths.append(folder/'period_calls.json')
        paths.append(ROOT/t['evidence_path'])
    save(P/'freeze.json',dict(source=source_version(ROOT),snapshot=snapshot(ROOT,P/'code_snapshot'),
        inputs={str(p.relative_to(ROOT)):sha(p) for p in paths},
        files={n:sha(P/n) for n in ['tasks.json','jobs.json','protocol.json']}))

def verify():
    f=read(P/'freeze.json');assert source_version(ROOT)['sha256']==f['source']['sha256']
    for name,h in f['inputs'].items():assert sha(ROOT/name)==h,name
    for name,h in f['files'].items():assert sha(P/name)==h,name

async def setup(task,out):
    from runtime_adapter import assemble
    from phase1_request_policy import ReportRequest
    old=OLD/'runs'/(task['id']+'_report_system_1')
    runtime,evidence=assemble(out,ReportRequest(**task['request']),None,[],[],None,BUDGET,
        frozen_evidence=read(ROOT/task['evidence_path']),length_control='enforce',calculation_control='tool',report_validation='enforce')
    await evidence._call('retrieve_uploaded_documents',{});await evidence._call('retrieve_web_documents',{})
    evidence.calculation_calls=read(old/'calculation_calls.json')
    evidence.period_calls=read(old/'period_calls.json') if(old/'period_calls.json').exists() else []
    save(out/'seed_calculation_calls.json',evidence.calculation_calls)
    save(out/'seed_period_calls.json',evidence.period_calls)
    save(out/'calculation_calls.json',evidence.calculation_calls)
    save(out/'evidence_ledger.json',evidence.sources)
    assert [(s['citation'],s['text']) for s in evidence.sources]==[(s['citation'],s['text']) for s in read(old/'evidence_ledger.json')]
    return runtime,evidence

async def offline():
    verify();records=[]
    for task in read(P/'tasks.json'):
        out=P/'offline'/task['id'];out.mkdir(parents=True,exist_ok=False)
        runtime,evidence=await setup(task,out)
        try:
            old=OLD/'runs'/(task['id']+'_report_system_1');draft=(old/'evaluated_report.md').read_text()
            feedback=evidence.validate_candidate(draft)
            semantic=validate_narrative(draft,evidence.calculation_calls,evidence.sources)
            codes=[i['code'] for i in semantic]
            expected=[CASES[task['id']]] if task['id'] in CASES else []
            from customization import measure_report_length
            length=measure_report_length(draft,evidence.request)
            records.append(dict(task_id=task['id'],known_failure=bool(expected),expected_codes=expected,
                codes=codes,detection_matches=sorted(codes)==expected,full_validation=feedback,
                length=length,original_sha256=sha(old/'evaluated_report.md')))
        finally:await runtime.aclose()
    save(P/'offline_results.json',records)
    assert all(r['detection_matches'] for r in records)
    assert all(r['full_validation']['passed'] for r in records if not r['known_failure'])
    print(json.dumps(dict(offline_reports=len(records),known_failures_detected=sum(r['known_failure'] for r in records),normal_controls_passed=sum(r['full_validation']['passed'] for r in records))),flush=True)

async def replay(job):
    from runtime_config import provider_settings
    from autoresearch_agent_core import AgentInput,MessageRecord
    verify();assert provider_settings()['model']=='Qwen3.8-27B'
    task=next(t for t in read(P/'tasks.json') if t['id']==job['task_id'])
    old=OLD/'runs'/job['run_id'];out=P/'runs'/job['run_id'];out.mkdir(parents=True,exist_ok=False)
    start=time.monotonic();runtime=None
    manifest={**job,'started_utc':now(),'status':'started','model':provider_settings()['model'],'budget':BUDGET,
        'source_sha256':read(P/'freeze.json')['source']['sha256'],'original_report_sha256':sha(old/'evaluated_report.md')}
    save(out/'run_manifest.json',manifest)
    for name in ('raw_report.md','evaluated_report.md','final_answer.md'):(out/name).write_text('')
    save(out/'request.json',task['request']);save(out/'agent_input.json',task['common_input'])
    try:
        runtime,evidence=await setup(task,out);draft=(old/'evaluated_report.md').read_text()
        feedback=evidence.validate_candidate(draft);save(out/'initial_feedback.json',feedback)
        context=dict(action='Repair the identified inconsistencies in this existing report. Preserve its verified tables, requested business topics, citations, structure and user length constraints. Correct the full paragraph where needed so the prose remains coherent. Submit the complete report through write_file, then return a short receipt. Do not regenerate unrelated sections.',
            original_draft=draft,save_validation=feedback,
            admitted_calculations=evidence.calculation_calls,admitted_date_comparisons=evidence.period_calls,
            admitted_sources=evidence.sources)
        save(out/'repair_input.json',context)
        result=await runtime.arun(AgentInput(messages=(MessageRecord(role='user',content=json.dumps(task['common_input'])),
            MessageRecord(role='user',content=json.dumps(context)))),run_id='execution')
        save(out/'runtime_output.json',result.model_dump(mode='json'))
        (out/'trajectory.jsonl').write_text(''.join(json.dumps(e.model_dump(mode='json'))+'\n' for e in result.trajectory))
        (out/'final_answer.md').write_text(result.final_answer or '')
        report=(out/'raw_report.md').read_text();(out/'evaluated_report.md').write_text(report)
        save(out/'evidence_ledger.json',evidence.sources)
        remaining=validate_narrative(report,evidence.calculation_calls,evidence.sources) if report else []
        save(out/'remaining_narrative_issues.json',remaining)
        manifest.update(status=result.status,terminal=result.terminal.model_dump(mode='json'),delivered=bool(report.strip()),
            report_origin='saved_file',remaining_detected_errors=len(remaining),
            usage=result.usage.model_dump() if result.usage else None,model_calls=sum(e.type=='model_completed' for e in result.trajectory),
            tool_calls=len(result.tool_calls),report_sha256=sha(out/'evaluated_report.md'))
    except Exception as exc:
        manifest.update(status='failed',error_type=type(exc).__name__,delivered=False)
        raise
    finally:
        if runtime:await runtime.aclose()
        manifest['elapsed_seconds']=round(time.monotonic()-start,3);save(out/'run_manifest.json',manifest)
    print(json.dumps({k:manifest.get(k) for k in ['task_id','status','delivered','model_calls','remaining_detected_errors']}),flush=True)

async def run():
    from runtime_config import load_project_environment
    load_project_environment();verify();assert not(P/'execution.json').exists()
    await offline();save(P/'execution.json',dict(started_utc=now(),workers=2))
    sem=asyncio.Semaphore(2)
    async def bounded(j):
        async with sem:await replay(j)
    await asyncio.gather(*(bounded(j) for j in read(P/'jobs.json')))
    verify();save(P/'execution_complete.json',dict(completed_utc=now(),new_model_runs=4,unchanged_gate_controls=12))

def rules():
    import evaluate_system_comparison as e
    import adjudicate_system_comparison as a
    e.P=P;e.ARMS=('report_system',);e.verify=verify;e.evaluate_rules()
    a.P=P;a.ARMS=('report_system',);a.adjudicate()
    # The reused evaluator was written for a 64-run study; use the actual plan.
    summary=read(P/'rule_summary.json');summary['planned']=len(read(P/'jobs.json'));save(P/'rule_summary.json',summary)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['prepare','verify','run','rules']);args=ap.parse_args()
    if args.action=='run':asyncio.run(run())
    else:globals()[args.action]()
