"""Fixed final development batch with missing business-topic coverage checks."""
import argparse,asyncio,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from experiments import report_optimization as base
from experiments.system_comparison import read,save,sha,now,BUDGET
base.P=ROOT/'artifacts/report_study/system_optimization_09';P=base.P

def prepare():
    base.prepare();p=read(P/'protocol.json')
    p.update(purpose='Validate factual, formatting and missing-topic completion after report-system optimization.',
        previous_development_batch='system_optimization_08',
        additional_changes=read(ROOT/'artifacts/report_study/system_optimization_08/protocol.json')['additional_changes']+[
            'For an explicitly requested company/quarter business topic with absent evidence, require a topical unavailable disclosure; earlier-period context does not substitute for the request'],
        selection='All 16 tasks once at this fixed version; no best-of selection across development batches.')
    save(P/'protocol.json',p);f=read(P/'freeze.json');f['files']['protocol.json']=sha(P/'protocol.json');save(P/'freeze.json',f)

async def replay():
    from runtime_adapter import assemble
    from runtime_config import load_project_environment
    from phase1_request_policy import ReportRequest
    from autoresearch_agent_core import AgentInput,MessageRecord
    from provenance import source_version
    load_project_environment();out=P/'coverage_failure_replay';out.mkdir(parents=True,exist_ok=False)
    old=ROOT/'artifacts/report_study/system_optimization_08/runs/costco_target_missing_report_system_1'
    request=ReportRequest(**read(old/'request.json'));common=read(old/'agent_input.json')
    task=next(t for t in read(ROOT/'artifacts/report_study/system_repair_04/tasks.json') if t['id']=='costco_target_missing')
    packet=read(ROOT/task['evidence_path']);draft=(old/'evaluated_report.md').read_text()
    save(out/'protocol.json',dict(started_utc=now(),scope='Replay of missing requested-topic disclosure. Prior report/sources/calculations supplied; excluded from the fresh 16-task scores.',source=source_version(ROOT),draft_sha256=sha(old/'evaluated_report.md')))
    runtime,evidence=assemble(out,request,None,[],[],None,BUDGET,frozen_evidence=packet)
    await evidence._call('retrieve_uploaded_documents',{});await evidence._call('retrieve_web_documents',{})
    evidence.calculation_calls=read(old/'calculation_calls.json');feedback=evidence.validate_candidate(draft)
    assert any(i['code']=='missing_business_topic_disclosure' for i in feedback['issues'])
    review=dict(draft=draft,save_validation=feedback,action='Correct the reported issue and resubmit the complete report.',
        calculation_results=[c['result'] for c in evidence.calculation_calls if 'error' not in c['result']])
    result=await runtime.arun(AgentInput(messages=(MessageRecord(role='user',content=json.dumps(common)),MessageRecord(role='user',content=json.dumps(review)))))
    await runtime.aclose();save(out/'runtime_output.json',result.model_dump(mode='json'))
    save(out/'result.json',dict(status=result.status,model_calls=sum(e.type=='model_completed' for e in result.trajectory),
        validation_passes=[c['passed'] for c in evidence.validation_checks],delivered=(out/'raw_report.md').exists()))
    print(json.dumps(read(out/'result.json')))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['replay','prepare','verify','run','rules','final']);a=ap.parse_args()
    if a.action=='prepare':prepare()
    elif a.action=='replay':asyncio.run(replay())
    elif a.action=='run':asyncio.run(base.run())
    elif a.action=='verify':base.verify()
    else:base.evaluate(a.action)
