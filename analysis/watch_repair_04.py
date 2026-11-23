"""Judge completed reports and import the unchanged external pilot outputs."""
import concurrent.futures,json,os,shutil,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
P=ROOT/'artifacts/report_study/system_repair_04'
OLD=ROOT/'artifacts/report_study/system_repair_03'
CHECKOUT=P/'checkout'
sys.path[:0]=[str(CHECKOUT/'analysis'),str(CHECKOUT),str(CHECKOUT/'src')]
from runtime_config import load_project_environment,provider_settings
from experiments.report_repair_comparison import verify
import evaluate_system_comparison as e
e.P=P;e.verify=verify;e.ARMS=('report_system','hermes_agent')
os.environ['DISSERTATION_ENV_FILE']=str(ROOT/'.env.local')
load_project_environment(role='judge')
e.save(P/'judge_execution.json',dict(started_utc=e.now(),model=provider_settings(role='judge')['model'],workers=2,
    blinding='No generating arm, internal gate state or paired report given to judge.'))
jobs=e.read(P/'jobs.json');pending={j['run_id']:j for j in jobs};results=[];futures={};references=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    while pending or futures:
        for id,j in list(pending.items()):
            target=P/'runs'/id
            if j['arm']=='hermes_agent' and not(target/'run_manifest.json').exists():
                source=OLD/'runs'/id
                if (source/'run_manifest.json').exists() and e.read(source/'run_manifest.json')['status']!='started':
                    shutil.copytree(source,target)
                    references.append(dict(run_id=id,source_batch='system_repair_03',
                        report_sha256=e.sha(source/'evaluated_report.md'),
                        source_manifest_sha256=e.sha(source/'run_manifest.json')))
                    e.save(P/'external_run_references.json',references)
            if len(futures)>=2:continue
            if (target/'run_manifest.json').exists() and e.read(target/'run_manifest.json')['status']!='started':
                task=next(t for t in e.read(P/'tasks.json') if t['id']==j['task_id'])
                assert e.read(target/'agent_input.json')==task['common_input']
                futures[pool.submit(e.judge_one,j)]=id
                del pending[id]
        for f,id in list(futures.items()):
            if f.done():
                results.append(f.result());del futures[f]
                e.save(P/'judge_results.json',results)
                print(json.dumps({'judged':len(results),'remaining':len(pending)+len(futures)}),flush=True)
        if pending or futures:time.sleep(3)
e.save(P/'execution_complete.json',dict(completed_utc=e.now(),runs=len(jobs),external_baseline_reused=16))
verify()
