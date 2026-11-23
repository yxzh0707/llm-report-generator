"""Prospective new-issuer report comparison, frozen before any generated report."""
import argparse,asyncio,json,random,shutil,subprocess,sys
from pathlib import Path
from decimal import Decimal,ROUND_HALF_UP
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'src'),str(ROOT/'analysis')]
from experiments import system_comparison as original,report_repair_comparison as hermes
from experiments.system_comparison import read,save,sha,now,norm,BUDGET
from provenance import source_version,snapshot,digest
P=ROOT/'artifacts/report_study/heldout_comparison_14'
ARMS=('report_system','hermes_agent')
NAMES=dict(servicenow='ServiceNow',intuit='Intuit',homedepot='Home Depot',lowes="Lowe's")
TOPICS={
 'servicenow':('current remaining performance obligations, distinguishing reported and constant-currency growth',
 'current remaining performance obligations (“cRPO”), contract revenue that will be recognized as revenue in the next 12 months, was $10.27 billion, representing 19% year-over-year growth and 22% in constant currency.'),
 'intuit':('Online Ecosystem revenue growth, distinguishing quarterly and full-year growth',
 'Online Ecosystem revenue grew 18 percent for the quarter and 20 percent for the year.'),
 'homedepot':('the extra week and comparable-sales performance, distinguishing total and U.S. comparable sales',
 'Comparable sales for the fourth quarter of fiscal 2024 increased 0.8%, and comparable sales in the U.S. increased 1.3%.'),
 'lowes':('the reported comparable-sales change and management explanation of its drivers',
 'Comparable sales for the quarter increased 0.2%, driven by high- single-digit Pro and online comparable sales, strong holiday performance, and rebuilding efforts in the wake of recent hurricanes, partially offset by continued near-term pressure in DIY discretionary spending.')}

def prepare():
    from phase1_request_policy import ReportRequest,required_headings
    from customization import STYLE_RULES,DEPTH_RULES
    assert not(P/'freeze.json').exists()
    # Production source is the previous repair, not tuned on the new evidence.
    previous=read(ROOT/'artifacts/report_study/precision_scope_13/freeze.json')['source']['files']
    assert all(sha(ROOT/n)==h for n,h in previous.items() if n.startswith('src/'))
    selection=read(P/'selection.json');gold={g['id']:g for g in read(P/'source_gold.json')}
    tasks=[];jobs=[];inventory=[]
    for a,b in selection['pairs']:
        pair=a+'_'+b;packet=dict(source_mode='hybrid',uploaded=[],web=[],retrieval=dict(mode='frozen_full_original',live_network=False))
        for c,kind in [(a,'uploaded'),(b,'web')]:
            for q in (3,4):
                id=c+f'_q{q}';folder=P/'sources'/id;record=read(folder/'record.json');text=(folder/'extracted.txt').read_text();h=digest(text.encode())
                assert record['complete_extraction'] and h==record['text_sha256']
                source=dict(source_kind=kind,document_id=id,title=f'{NAMES[c]} Q{q} FY2024 earnings release',
                    source_url=record['url'],retrieval_url=record['url'],fiscal_year=2024,fiscal_quarter=q,
                    text=text,text_sha256=h,excerpt_sha256=h,char_start=0,char_end=len(text),
                    chunk_id=id+':full',evidence_id=id+':full:'+h,file_sha256=h)
                packet[kind].append(source);inventory.append(dict(company=c,quarter=q,fiscal_year=2024,source_kind=kind,source_url=record['url'],characters=len(text),pages=record['page_count'],source_sha256=h))
        for profile in selection['profiles']:
            missing=profile=='missing';limit=600 if profile in ('brief','missing') else None
            structure='standard_analysis'if profile=='standard'else'comparative_analysis'
            style={'brief':'concise_briefing','missing':'concise_briefing','standard':'formal_analytical','detailed':'detailed_explanatory'}[profile]
            depth='brief'if limit else'detailed'if profile=='detailed'else'standard'
            evidence={**packet,'web':[s for s in packet['web'] if not(missing and s['document_id']==b+'_q4')]}
            ep=P/'evidence'/(pair+('_missing'if missing else'_complete')+'.json');save(ep,evidence)
            na,nb=NAMES[a],NAMES[b]
            task=(f'Prepare an evidence-based business comparison of {na} and {nb} using their FY2024 Q3 and Q4 releases in the permitted source collection. '
                'Use only this complete collection of uploaded and archived web documents; no external search is required. '
                'Provide an executive conclusion and a useful cross-company analysis. '
                'Include a revenue table with columns Item | Revenue (USD billions) | Evidence and rows '+', '.join(f'{NAMES[c]} Q{q} revenue'for c in(a,b)for q in(3,4))+'. '
                'Use consolidated GAAP revenue (net sales where that is the issuer\'s revenue measure), in USD billions to two decimal places. '
                'Use the most precise amount in each current-quarter financial-statement table, rather than rounded headline amounts or prior-year columns. '
                'Each row must cite that company\'s own release for that quarter using [S#]. If an own-quarter release is absent, report Unavailable; do not fill it from another release or memory. '
                f'Also report {na} H2 revenue and {nb} H2 revenue as the sum of the displayed Q3 and Q4 values in USD billions to two decimal places. '
                f'Separately calculate {na} Q4 revenue change and {nb} Q4 revenue change: the percentage change from Q3 to Q4, using the original unrounded financial-statement amounts, to one decimal place. '
                'Use those exact labels in small tables or Label: value lines; report Unavailable for a calculation with a missing input. '
                f'Explain these business topics from the Q4 releases: {na}: {TOPICS[a][0]}; {nb}: {TOPICS[b][0]}. '
                'Retain the original period and distinguish results, management explanations and forecasts. If the relevant release is absent, explain that the requested update cannot be established. '
                'Identify fiscal-calendar and duration comparability from the actual documents, without assuming that all companies have different calendars. '
                'Explain limits of cross-company revenue comparisons; do not infer that larger revenue implies better profitability or investment quality. '
                'Cite material factual claims and include a Sources section. No investment recommendation is requested.')
            req=ReportRequest(task=task,structure=structure,style=style,depth=depth,source_mode='hybrid',max_words=limit)
            common=dict(task=task,language='English',output_format='Markdown',headings=list(required_headings(structure)),
                heading_rule='Use these level-two headings in the given order, with level-three subheadings when useful.',style=STYLE_RULES[style],depth=DEPTH_RULES[depth],
                length=f'At most {limit} body words including title, headings and tables; exclude Sources and [S#] IDs. Use a counting tool if needed.'if limit else'No numeric word limit. Let the requested style and depth determine length.',
                tools_note='Read the complete permitted uploaded and archived-web sources using your available tools. For file access, corpus/manifest.json lists source files and citation identifiers. Save the complete final report to work/outputs/final_report.md, then give a short receipt. If useful, count_words.py implements the body word-count rule.')
            expected=[];growth=[];highlights=[]
            for c in(a,b):
                for q in(3,4):
                    g=gold[c+f'_q{q}'];v=(Decimal(g['reported_value'])/1000).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
                    expected.append(dict(id=g['id'],label=f'{NAMES[c]} Q{q} revenue',value=None if missing and c==b and q==4 else str(v),source_id=g['id'],proof=g['proof']))
                q3,q4=(Decimal(gold[c+f'_q{q}']['reported_value'])for q in(3,4));v=((q4/q3-1)*100).quantize(Decimal('.1'),rounding=ROUND_HALF_UP)
                growth.append(dict(label=f'{NAMES[c]} Q4 revenue change',value=None if missing and c==b else str(v),unit='percent',raw_inputs=[str(q3),str(q4)]))
                text=next(s['text']for s in packet['uploaded']+packet['web']if s['document_id']==c+'_q4');assert norm(TOPICS[c][1])in norm(text),c
                highlights.append(dict(company=NAMES[c],source_id=c+'_q4',topic=TOPICS[c][0],reference_quote=TOPICS[c][1],available=not(missing and c==b)))
            tid=pair+'_'+profile;tasks.append(dict(id=tid,pair=pair,profile=profile,request=req.__dict__,common_input=common,evidence_path=str(ep.relative_to(ROOT)),expected=expected,growth=growth,highlights=highlights))
            for arm in ARMS:
                for rep in ((1,2)if profile in selection['repeated_profiles']else(1,)):
                    jobs.append(dict(run_id=f'{tid}_{arm}_{rep}',task_id=tid,arm=arm,repetition=rep))
    assert len(tasks)==8 and len(jobs)==24
    save(P/'tasks.json',tasks);save(P/'jobs.json',jobs);save(P/'inventory.json',inventory)
    save(P/'protocol.json',dict(created_utc=now(),status='frozen_before_generation',new_issuers=True,new_fiscal_periods=True,
        primary='Correct source-grounded requested facts/business topics and user output requirements; report numeric, semantic, instruction and delivery outcomes separately.',
        secondary='Displayed-input sums versus raw-input growth, period comparison, repeated-run stability and measured resource use.',
        companies=4,unique_documents=8,archived_web_documents=4,uploaded_documents=4,tasks=8,repeated_profiles=selection['repeated_profiles'],runs=24,
        production_source_unchanged_since='precision_scope_13',model='Qwen3.8-27B',temperature=.2,thinking=False,
        arms={'report_system':'Frozen production runtime with source binding, deterministic calculation/counting and save/rework gates.',
              'hermes_agent':'Installed native Hermes, original prompt, terminal/file/todo tools, fresh isolated profile; same Qwen and identical user payload/full source texts.'},
        hermes_commit=subprocess.check_output(['git','-C',str(hermes.HERMES),'rev-parse','HEAD'],text=True).strip(),
        budget={'report_system':BUDGET,'hermes_agent':dict(native_max_iterations=16,wall_seconds=900,max_tokens=12000)},
        budget_note='Native iteration and closing-summary accounting differ. Report observed counts, not exact equal total budget or billed-cost advantage.',
        evaluation='External fixed source table references and Decimal arithmetic; blinded DeepSeek rubric; audit all quote flags and both-arm narratives for period/metric/ratio inconsistencies. Internal gate pass is not a quality outcome.',
        grouping='Report all 24 runs; separate first runs from four prespecified task repeats per arm. Two company pairs are clusters; no independence assumption for facts or repeated reports.',
        stop='No changes to source code, user tasks, evidence or criteria after generation begins. Every planned attempt retained; no post-outcome substitutions or best-of pooling.',
        acquisition='Controlled report-generation experiment. Complete extracted original texts shared; live retrieval is outside this comparison.',
        source=snapshot(ROOT,P/'code_snapshot')))
    inputs=[p for d in ['sources','evidence']for p in(P/d).rglob('*')if p.is_file()]
    inputs += [P/n for n in ['selection.json','source_gold.json','tasks.json','jobs.json','inventory.json','protocol.json']]
    analysis=['evaluate_system_comparison.py','adjudicate_system_comparison.py','normalize_system_judge_quotes.py','evaluate_heldout_reports.py']
    for n in analysis:
        target=P/'analysis_code'/n;target.parent.mkdir(exist_ok=True);shutil.copy2(ROOT/'analysis'/n,target)
    save(P/'freeze.json',dict(source=source_version(ROOT),inputs={str(p.relative_to(ROOT)):sha(p)for p in inputs},analysis={n:sha(ROOT/'analysis'/n)for n in analysis}))

def verify():
    f=read(P/'freeze.json');assert source_version(ROOT)['sha256']==f['source']['sha256']
    for n,h in f['inputs'].items():assert sha(ROOT/n)==h,n
    for n,h in f['analysis'].items():assert sha(ROOT/'analysis'/n)==h,n

async def run():
    verify();assert not(P/'execution.json').exists()
    original.P=hermes.P=P;original.verify=hermes.verify=verify
    jobs=read(P/'jobs.json');random.Random(2026102801).shuffle(jobs)
    save(P/'execution.json',dict(started_utc=now(),workers=2,order=[j['run_id']for j in jobs]))
    sem=asyncio.Semaphore(2)
    async def one(j):
        async with sem:await(original.run_job(j)if j['arm']=='report_system'else hermes.hermes_job(j))
    await asyncio.gather(*(one(j)for j in jobs));verify()
    save(P/'execution_complete.json',dict(completed_utc=now(),runs=len(jobs)))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['prepare','verify','run']);a=ap.parse_args()
    if a.action=='run':asyncio.run(run())
    else:globals()[a.action]()
