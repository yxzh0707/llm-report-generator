"""Development repair replication, followed by an external Hermes pilot.

The previous 64-run study is immutable. This batch is a one-repeat development
comparison on its 16 tasks, not a held-out confirmation of general superiority.
"""
import argparse,asyncio,json,os,random,sys,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from experiments import system_comparison as original
from provenance import source_version,snapshot
from experiments.system_comparison import read,save,sha,now

P=ROOT/'artifacts/report_study/system_repair_03'
PREVIOUS=ROOT/'artifacts/report_study/system_comparison_02'
HERMES=Path(os.environ.get('HERMES_SOURCE', str(Path.home()/'.hermes/hermes-agent'))).expanduser()
ARMS=('report_system','hermes_agent')

def prepare():
    assert not(P/'protocol.json').exists()
    P.mkdir(parents=True,exist_ok=True)
    tasks=read(PREVIOUS/'tasks.json')
    for t in tasks:
        t['common_input']['tools_note']='Read the complete permitted uploaded and archived-web sources using your available tools. For file access, corpus/manifest.json lists the source files and citation identifiers. Save the complete final report to work/outputs/final_report.md, then give a short receipt. If useful, count_words.py implements the body word-count rule.'
    save(P/'tasks.json',tasks)
    jobs=[dict(run_id=t['id']+'_'+arm+'_1',task_id=t['id'],arm=arm,repetition=1) for arm in ARMS for t in tasks]
    save(P/'jobs.json',jobs)
    commit=subprocess.check_output(['git','-C',str(HERMES),'rev-parse','HEAD'],text=True).strip()
    save(P/'protocol.json',dict(created_utc=now(),status='frozen_before_generation',
        purpose='Repair known deterministic failures, then compare against installed Hermes Agent on the same Qwen and tasks.',
        previous_study=str(PREVIOUS.relative_to(ROOT)),development_not_heldout=True,
        arms={'report_system':'Repaired production runtime, deterministic presentation and section checks.',
              'hermes_agent':'Installed unmodified AIAgent; stock terminal, file and todo tools; original system prompt; fresh per-task profile.'},
        model='Qwen3.8-27B',temperature=0.2,thinking=False,max_output_tokens=12000,
        budget={'report_system':original.BUDGET,'hermes_agent':{'native_max_iterations':16,'wall_seconds':900,'terminal_timeout_seconds':60}},
        budget_note='Hermes uses native iteration accounting and native tool calls; actual model/tool counts are retained. This pilot does not assume identical accounting across frameworks.',
        hermes_commit=commit,runs=len(jobs),tasks=16,repetitions=1,
        acquisition='Frozen complete sources, no live discovery. Hermes receives local source files; report system receives the same texts through source tools.',
        evaluation='Same external rules, disclosed source alternatives and blinded DeepSeek criteria; source quotations must be audited. Internal gate status is not a quality score.',
        stop='Retain every planned run; no tuning after viewing this batch. Compatibility smoke uses synthetic evidence.',
        source=snapshot(ROOT,P/'code_snapshot')))
    save(P/'freeze.json',{'source':source_version(ROOT),'tasks_sha256':sha(P/'tasks.json'),'jobs_sha256':sha(P/'jobs.json'),
        'evidence':{t['evidence_path']:sha(ROOT/t['evidence_path']) for t in tasks}})

def verify():
    f=read(P/'freeze.json')
    for name,h in f['source']['files'].items():
        assert sha(ROOT/name)==h,name
    assert sha(P/'tasks.json')==f['tasks_sha256'] and sha(P/'jobs.json')==f['jobs_sha256']
    for name,h in f['evidence'].items():assert sha(ROOT/name)==h,name

def workspace(out,packet):
    work=out/'workspace';(work/'corpus').mkdir(parents=True)
    ledger=[]
    for s in packet['uploaded']+packet['web']:
        s={**s,'citation':f'[S{len(ledger)+1}]'};ledger.append(s)
        (work/'corpus'/(s['document_id']+'.md')).write_text(s['citation']+' '+s['title']+'\n'+s['source_url']+'\n\n'+s['text'])
    save(work/'corpus/manifest.json',[{k:s[k] for k in ['document_id','citation','title','source_kind','source_url']}|{'path':'corpus/'+s['document_id']+'.md'} for s in ledger])
    (work/'count_words.py').write_text('import re,sys\nfrom pathlib import Path\ns=Path(sys.argv[1]).read_text()\ns=re.split(r"^#{1,6} Sources\\s*$",s,maxsplit=1,flags=re.M)[0]\ns=re.sub(r"\\[S\\d+\\]","",s)\nprint(len(re.findall(r"\\b[\\w\x27-]+\\b",s)))\n')
    save(out/'evidence_ledger.json',ledger)

async def hermes_job(j):
    verify();t=next(t for t in read(P/'tasks.json') if t['id']==j['task_id'])
    out=P/'runs'/j['run_id'];out.mkdir(parents=True,exist_ok=False)
    save(out/'agent_input.json',t['common_input']);save(out/'request.json',t['request'])
    workspace(out,read(ROOT/t['evidence_path']))
    manifest={**j,'started_utc':now(),'status':'started','model':'Qwen3.8-27B'};save(out/'run_manifest.json',manifest)
    start=time.monotonic()
    with (out/'worker.log').open('w') as log:
        p=await asyncio.create_subprocess_exec(str(HERMES/'venv/bin/python'),str(ROOT/'experiments/hermes_report_worker.py'),str(out),stdout=log,stderr=log)
        try:code=await asyncio.wait_for(p.wait(),900)
        except asyncio.TimeoutError:p.kill();await p.wait();code=-1
    if not(out/'evaluated_report.md').exists():(out/'evaluated_report.md').write_text('')
    usage=read(out/'hermes_usage.json') if(out/'hermes_usage.json').exists() else {}
    manifest.update(status='succeeded' if code==0 else 'failed',exit_code=code,
        delivered=bool((out/'evaluated_report.md').read_text().strip()),elapsed_seconds=round(time.monotonic()-start,3),
        model_calls=usage.get('session_api_calls'),usage={'total_tokens':usage.get('session_total_tokens')},
        report_sha256=sha(out/'evaluated_report.md'))
    save(out/'run_manifest.json',manifest)
    print(json.dumps({k:manifest[k] for k in ['run_id','status','delivered','model_calls','elapsed_seconds']}),flush=True)

async def run(arm):
    verify();jobs=[j for j in read(P/'jobs.json') if j['arm']==arm]
    original.P=P;original.verify=verify
    sem=asyncio.Semaphore(2)
    async def one(j):
        if (P/'runs'/j['run_id']/'run_manifest.json').exists():return
        async with sem:
            await (original.run_job(j) if arm=='report_system' else hermes_job(j))
    await asyncio.gather(*(one(j) for j in jobs))
    save(P/(arm+'_complete.json'),dict(completed_utc=now(),runs=len(jobs)))
    if all((P/(a+'_complete.json')).exists() for a in ARMS):save(P/'execution_complete.json',dict(completed_utc=now(),runs=32))

def evaluate(action):
    sys.path.insert(0,str(ROOT/'analysis'))
    import evaluate_system_comparison as e
    import adjudicate_system_comparison as a
    e.P=a.P=P;e.ARMS=a.ARMS=ARMS;e.verify=verify
    if action=='rules':e.evaluate_rules();a.adjudicate()
    elif action=='judge':e.judge()
    else:a.finalize()

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['prepare','verify','report_system','hermes_agent','rules','judge','final']);args=ap.parse_args()
    if args.action in ARMS:asyncio.run(run(args.action))
    elif args.action in {'prepare','verify'}:globals()[args.action]()
    else:evaluate(args.action)
