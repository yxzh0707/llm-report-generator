"""Evaluate completed immutable reports while remaining frozen jobs execute."""
import concurrent.futures,time,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from evaluate_system_comparison import judge_one,P,read,save,now,verify
from runtime_config import load_project_environment,provider_settings

verify();load_project_environment(role='judge');model=provider_settings(role='judge')['model']
assert 'deepseek' in model.lower()
save(P/'judge_execution.json',{'started_utc':now(),'model':model,'workers':2,
    'mode':'Completed reports evaluated concurrently with remaining frozen generation; no prompt/task/runtime changes or judge feedback to generator.',
    'blinding':'No arm, system prompt, internal gate state, paired report or runtime outcome supplied.'})
jobs=read(P/'jobs.json');submitted=set();results=[];pending={}
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    while len(results)<len(jobs):
        verify()
        for j in jobs:
            if len(pending)>=2:break
            if j['run_id'] in submitted:continue
            p=P/'runs'/j['run_id']/'run_manifest.json'
            if p.exists() and read(p)['status']!='started':
                pending[pool.submit(judge_one,j)]=j['run_id'];submitted.add(j['run_id'])
        done=[f for f in pending if f.done()]
        for f in done:
            try:results.append(f.result())
            except Exception as e:results.append({'run_id':pending[f],'status':'unresolved','error_type':type(e).__name__})
            del pending[f];save(P/'judge_results.json',results)
        if len(results)<len(jobs):time.sleep(3)
save(P/'judge_complete.json',{'completed_utc':now(),'reports':len(results)})
