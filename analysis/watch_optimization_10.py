"""Score only new completed system reports; retain sealed baseline assessments."""
import concurrent.futures,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'src'),str(ROOT/'analysis')]
from experiments.report_adaptive_completion import base
P,ARMS,verify=base.P,base.ARMS,base.verify
from runtime_config import load_project_environment,provider_settings
import evaluate_system_comparison as e
e.P=P;e.ARMS=ARMS;e.verify=verify
load_project_environment(role='judge')
e.save(P/'judge_execution.json',dict(started_utc=e.now(),model=provider_settings(role='judge')['model'],workers=2,
    blinding='Generator arm, prompt and gate results excluded; same single-report rubric as frozen baseline.',
    baseline_assessments_reused=16,new_assessments=16))
pending={j['run_id']:j for j in e.read(P/'jobs.json') if j['arm']=='report_system'}
results=e.read(P/'judge_results.json');futures={}
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    while pending or futures:
        for id,j in list(pending.items()):
            if len(futures)>=2:break
            folder=P/'runs'/id
            if (folder/'run_manifest.json').exists() and e.read(folder/'run_manifest.json')['status']!='started':
                futures[pool.submit(e.judge_one,j)]=id;del pending[id]
        for f,id in list(futures.items()):
            if f.done():
                results=[r for r in results if r['run_id']!=id]+[f.result()];del futures[f]
                e.save(P/'judge_results.json',results)
        if pending or futures:time.sleep(3)
verify()
