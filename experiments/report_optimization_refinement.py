"""Second fixed development batch: actionable source repair and metric scope."""
import argparse,asyncio,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from experiments import report_optimization as base
from experiments.system_comparison import read,save,sha,now,BUDGET
base.P=ROOT/'artifacts/report_study/system_optimization_06'
P=base.P

def prepare():
    base.prepare()
    protocol=read(P/'protocol.json')
    protocol.update(purpose='Complete the repair loop with original table-row candidates, explicit metric-basis checks and precise date-claim matching.',
        previous_development_batch='system_optimization_05',
        additional_changes=['Return literal candidate rows, unit headers and column context on source-binding errors',
            'Focused calculation repair within the existing call budget; stop after three failed plans',
            'Check an explicit include-membership-fees request against the Total revenue row for the named company',
            'Distinguish quarter duration from quantified offsets; select matching quarter comparisons'],
        selection='All 16 system tasks generated once with this fixed version. Do not pool best reports across development batches.')
    save(P/'protocol.json',protocol)
    freeze=read(P/'freeze.json');freeze['files']['protocol.json']=sha(P/'protocol.json');save(P/'freeze.json',freeze)

async def replay():
    from runtime_adapter import assemble
    from runtime_config import load_project_environment
    from phase1_request_policy import ReportRequest
    from autoresearch_agent_core import AgentInput,MessageRecord
    from provenance import source_version
    load_project_environment()
    old=ROOT/'artifacts/report_study/system_optimization_05/runs/ibm_netflix_detailed_report_system_1'
    out=P/'failure_replay';out.mkdir(parents=True,exist_ok=False)
    request=ReportRequest(**read(old/'request.json'));common=read(old/'agent_input.json')
    task=next(t for t in read(ROOT/'artifacts/report_study/system_repair_04/tasks.json') if t['id']=='ibm_netflix_detailed')
    packet=read(ROOT/task['evidence_path'])
    save(out/'protocol.json',dict(started_utc=now(),scope='Development replay starting at the first rejected calculator plan; not a fresh task or part of the 16-task score.',source=source_version(ROOT)))
    runtime,evidence=assemble(out,request,None,[],[],None,BUDGET,frozen_evidence=packet)
    contexts=[await evidence._call('retrieve_uploaded_documents',{}),await evidence._call('retrieve_web_documents',{})]
    call=read(old/'calculation_calls.json')[0]
    evidence.calculate(call['arguments'])
    result=await runtime.arun(AgentInput(messages=(MessageRecord(role='user',content=json.dumps(common)),
        MessageRecord(role='user',content='Previously read source tool outputs:\n'+'\n'.join(contexts)))))
    await runtime.aclose();save(out/'runtime_output.json',result.model_dump(mode='json'))
    save(out/'result.json',dict(status=result.status,terminal=result.terminal.model_dump(mode='json'),
        model_calls=sum(e.type=='model_completed' for e in result.trajectory),
        repaired=any('error' not in c['result'] for c in evidence.calculation_calls),
        delivered=(out/'raw_report.md').exists()))
    print(json.dumps(read(out/'result.json')))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['replay','prepare','verify','run','rules','final']);a=ap.parse_args()
    if a.action=='prepare':prepare()
    elif a.action=='replay':asyncio.run(replay())
    elif a.action=='run':asyncio.run(base.run())
    elif a.action=='verify':base.verify()
    else:base.evaluate(a.action)
