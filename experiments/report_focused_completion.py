"""Fixed development batch with structured narrative editing and typography-safe binding."""
import argparse,asyncio,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from experiments import report_optimization as base
from experiments.system_comparison import read,save,sha,now,BUDGET
base.P=ROOT/'artifacts/report_study/system_optimization_08';P=base.P

def prepare():
    base.prepare();p=read(P/'protocol.json')
    p.update(purpose='Validate focused paragraph editing together with source-grounded calculation repair.',
        previous_development_batch='system_optimization_07',
        additional_changes=read(ROOT/'artifacts/report_study/system_optimization_07/protocol.json')['additional_changes']+[
            'Program selects one narrative block and its local word target; same Qwen model edits only that block within the existing call budget',
            'Match quantified calendar gaps to the nearest explicit quarter in multi-comparison sentences'],
        selection='All 16 tasks once at this fixed version; no best-of selection across development batches.')
    save(P/'protocol.json',p);f=read(P/'freeze.json');f['files']['protocol.json']=sha(P/'protocol.json');save(P/'freeze.json',f)

async def replay():
    from runtime_adapter import assemble
    from runtime_config import load_project_environment
    from phase1_request_policy import ReportRequest
    from autoresearch_agent_core import AgentInput,MessageRecord
    from provenance import source_version
    load_project_environment();out=P/'length_failure_replay_02';out.mkdir(parents=True,exist_ok=False)
    old=ROOT/'artifacts/report_study/system_optimization_07/runs/adobe_salesforce_missing_report_system_1'
    request=ReportRequest(**read(old/'request.json'));common=read(old/'agent_input.json')
    task=next(t for t in read(ROOT/'artifacts/report_study/system_repair_04/tasks.json') if t['id']=='adobe_salesforce_missing')
    packet=read(ROOT/task['evidence_path']);checks=read(old/'length_checks.json');candidate=old/checks[-1]['candidate']
    save(out/'protocol.json',dict(started_utc=now(),scope='Development replay of the exact repeatedly rejected over-limit draft, with previously admitted sources/calculations. Excluded from 16-task scores.',source=source_version(ROOT),original_candidate_sha256=sha(candidate)))
    runtime,evidence=assemble(out,request,None,[],[],None,BUDGET,frozen_evidence=packet)
    await evidence._call('retrieve_uploaded_documents',{});await evidence._call('retrieve_web_documents',{})
    evidence.calculation_calls=read(old/'calculation_calls.json')
    evidence.check_length(candidate.read_text(),'replayed_rejected_draft')
    result=await runtime.arun(AgentInput(messages=(MessageRecord(role='user',content=json.dumps(common)),)))
    await runtime.aclose();save(out/'runtime_output.json',result.model_dump(mode='json'))
    save(out/'result.json',dict(status=result.status,terminal=result.terminal.model_dump(mode='json'),
        model_calls=sum(e.type=='model_completed' for e in result.trajectory),
        counts=[x['body_words'] for x in evidence.length_checks],delivered=(out/'raw_report.md').exists()))
    print(json.dumps(read(out/'result.json')))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['replay','prepare','verify','run','rules','final']);a=ap.parse_args()
    if a.action=='prepare':prepare()
    elif a.action=='replay':asyncio.run(replay())
    elif a.action=='run':asyncio.run(base.run())
    elif a.action=='verify':base.verify()
    else:base.evaluate(a.action)
