"""Development optimization; reuse the sealed Hermes outputs, never regenerate them."""
import argparse,asyncio,json,random,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from experiments import system_comparison as original
from experiments.system_comparison import read,save,sha,now
from provenance import snapshot,source_version,digest
P=ROOT/'artifacts/report_study/system_optimization_05'
PREVIOUS=ROOT/'artifacts/report_study/system_repair_04'
ARMS=('report_system','hermes_agent')

def verify_previous():
    files=read(PREVIOUS/'analysis_manifest.json')['files']
    for name,h in files.items():assert sha(PREVIOUS/name)==h,name
    return dict(files=len(files),all_passed=True,manifest_sha256=sha(PREVIOUS/'analysis_manifest.json'))

def prepare():
    assert not(P/'protocol.json').exists()
    saved=verify_previous()
    tasks=read(PREVIOUS/'tasks.json');jobs=read(PREVIOUS/'jobs.json')
    save(P/'tasks.json',tasks);save(P/'jobs.json',jobs)
    save(P/'baseline_seal_verification.json',saved)
    references=[]
    for j in jobs:
        if j['arm']!='hermes_agent':continue
        source=PREVIOUS/'runs'/j['run_id'];target=P/'runs'/j['run_id']
        shutil.copytree(source,target)
        shutil.copytree(PREVIOUS/'judge'/j['run_id'],P/'judge'/j['run_id'])
        references.append(dict(run_id=j['run_id'],source_batch='system_repair_04',original_generation_batch='system_repair_03',
            report_sha256=sha(source/'evaluated_report.md'),manifest_sha256=sha(source/'run_manifest.json')))
    save(P/'external_run_references.json',references)
    save(P/'judge_results.json',[r for r in read(PREVIOUS/'judge_results.json') if '_hermes_agent_' in r['run_id']])
    save(P/'semantic_adjudications.json',[r for r in read(PREVIOUS/'semantic_adjudications.json') if '_hermes_agent_' in r['run_id']])
    save(P/'protocol.json',dict(created_utc=now(),status='frozen_before_generation',
        purpose='Repair source-number pre-rounding, repetitive over-limit revision and unsupported fiscal-date arithmetic.',
        development_not_heldout=True,model='Qwen3.8-27B',temperature=0.2,thinking=False,
        size=dict(companies=8,documents=16,tasks=16,new_system_runs=16,reused_baseline_runs=16),
        shared_user_inputs='Identical to the sealed system_repair_04 task payloads and existing Hermes rollouts.',
        changes=['Original quoted monetary token and same-source unit binding before conversion',
                 'Focused revision context with actual word counts and section budgets; unchanged failure is bounded',
                 'Source-bound reporting-date arithmetic for quantified fiscal offsets'],
        arms={'report_system':'Production runtime with the above optimization.',
              'hermes_agent':'Unmodified local Hermes using internal Qwen; original rollout and its adjudicated assessment reused.'},
        budget=original.BUDGET,
        external_baseline_budget_note='Hermes native 16 iterations; its closing-summary calls and token accounting differ. Preserve prior audit; no strict equal billed-budget claim.',
        evaluation='Same external rules, disclosed source alternatives and blinded DeepSeek criteria as system_repair_04. Audit every quote flag and all reports. Internal checks are not evaluation scores.',
        stop='Run all 16 system tasks once, retain all outcomes; no prompt or runtime edits during the batch. Development fixes do not constitute held-out validation.',
        source=snapshot(ROOT,P/'code_snapshot')))
    analysis_files=['evaluate_system_comparison.py','adjudicate_system_comparison.py','normalize_system_judge_quotes.py']
    for name in analysis_files:
        target=P/'analysis_code'/name;target.parent.mkdir(exist_ok=True);shutil.copy2(ROOT/'analysis'/name,target)
    save(P/'freeze.json',dict(source=source_version(ROOT),files={name:sha(P/name) for name in ['tasks.json','jobs.json','protocol.json']},
        evidence={t['evidence_path']:sha(ROOT/t['evidence_path']) for t in tasks},
        analysis={name:sha(ROOT/'analysis'/name) for name in analysis_files}))

def verify():
    f=read(P/'freeze.json')
    assert source_version(ROOT)['sha256']==f['source']['sha256'],'Source changed after freeze'
    for name,h in f['files'].items():assert sha(P/name)==h,name
    for name,h in f['evidence'].items():assert sha(ROOT/name)==h,name
    for name,h in f['analysis'].items():assert sha(ROOT/'analysis'/name)==h,name
    for r in read(P/'external_run_references.json'):
        assert sha(P/'runs'/r['run_id']/'evaluated_report.md')==r['report_sha256']

async def run():
    verify();assert not(P/'execution.json').exists()
    original.P=P;original.verify=verify
    jobs=[j for j in read(P/'jobs.json') if j['arm']=='report_system'];random.Random(2026102717).shuffle(jobs)
    save(P/'execution.json',dict(started_utc=now(),workers=2,order=[j['run_id'] for j in jobs]))
    sem=asyncio.Semaphore(2)
    async def one(j):
        async with sem:await original.run_job(j)
    await asyncio.gather(*(one(j) for j in jobs));verify()
    save(P/'execution_complete.json',dict(completed_utc=now(),new_system_runs=16,reused_baseline_runs=16))

async def smoke():
    from phase1_request_policy import ReportRequest,required_headings
    out=P/'synthetic_smoke';assert not(out/'tasks.json').exists()
    sources=[]
    for i,text in enumerate(['Example company Q3 revenue was USD 12,345 million. The period ended January 31, 2025. Software subscriptions drove growth.',
                             'Example company Q4 revenue was USD 13,078 million. The period ended April 30, 2025. Services renewals drove growth.'],1):
        sources.append(dict(source_kind='web',document_id=f'example_q{i+2}',title=f'Example Q{i+2} FY2025',source_url=f'https://example.org/q{i+2}',
            retrieval_url=f'https://example.org/q{i+2}',text=text,text_sha256=digest(text.encode()),char_start=0,char_end=len(text),chunk_id=str(i),evidence_id=str(i)))
    task='Compare Example company Q3 and Q4 FY2025. Include rows Q3 revenue and Q4 revenue in USD billions to two decimal places, plus H2 revenue as the sum of the displayed Q3 and Q4 values. Explain the two growth drivers and state both period-end dates. Cite sources. Use the required headings.'
    req=ReportRequest(task=task,source_mode='web_only',max_words=180)
    common=dict(task=task,language='English',headings=list(required_headings(req.structure)),length='At most 180 body words, excluding Sources and citation IDs.')
    ep=out/'evidence.json';save(ep,dict(source_mode='web_only',uploaded=[],web=sources,retrieval={'mode':'frozen'}))
    save(out/'tasks.json',[dict(id='synthetic',request=req.__dict__,common_input=common,evidence_path=str(ep.relative_to(ROOT)))])
    save(out/'freeze.json',dict(source=source_version(ROOT)))
    original.P=out;original.verify=lambda:None
    await original.run_job(dict(run_id='synthetic_report_system_1',task_id='synthetic',arm='report_system',repetition=1))

def evaluate(action):
    sys.path.insert(0,str(ROOT/'analysis'))
    import evaluate_system_comparison as e
    import adjudicate_system_comparison as a
    e.P=a.P=P;e.ARMS=a.ARMS=ARMS;e.verify=verify
    if action=='rules':e.evaluate_rules();a.adjudicate()
    else:a.finalize()

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['smoke','prepare','verify','run','rules','final']);a=ap.parse_args()
    if a.action in {'run','smoke'}:asyncio.run(globals()[a.action]())
    elif a.action in {'rules','final'}:evaluate(a.action)
    else:globals()[a.action]()
