"""Apply the frozen blinded rubric as completed held-out reports arrive."""
import concurrent.futures,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'src'),str(ROOT/'analysis')]
from experiments.heldout_report_comparison import P,ARMS,verify
from experiments.system_comparison import read,save,now,sha
from runtime_config import load_project_environment,provider_settings
import evaluate_system_comparison as e
e.P=P;e.ARMS=ARMS;e.verify=verify
verify();load_project_environment(role='judge');assert 'deepseek' in provider_settings(role='judge')['model'].lower()
save(P/'judge_execution.json',dict(started_utc=now(),model=provider_settings(role='judge')['model'],workers=2,
    blinding='Arm, generator prompts, gate outcomes and paired reports excluded; exact frozen single-report rubric.',
    reused_assessments=0,planned_assessments=24,orchestrator_sha256=sha(Path(__file__))))
pending={j['run_id']:j for j in read(P/'jobs.json')};results=[];futures={}
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    while pending or futures:
        for id,j in list(pending.items()):
            if len(futures)>=2:break
            path=P/'runs'/id/'run_manifest.json'
            if path.exists() and read(path)['status']!='started':
                futures[pool.submit(e.judge_one,j)]=id;del pending[id]
        for f,id in list(futures.items()):
            if f.done():
                results.append(f.result());del futures[f];save(P/'judge_results.json',results)
        if pending or futures:time.sleep(3)
verify();save(P/'judge_complete.json',dict(completed_utc=now(),reports=len(results)))
