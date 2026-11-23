"""Fixed, external scoring for new-issuer report tasks."""
import argparse,json,re,sys
from decimal import Decimal
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'src'),str(ROOT/'analysis')]
from experiments.heldout_report_comparison import P,ARMS,NAMES,verify
from experiments.system_comparison import read,save,now
import evaluate_system_comparison as e
import adjudicate_system_comparison as a

def configure():
    e.P=a.P=P;e.ARMS=a.ARMS=ARMS;e.NAMES=NAMES;e.verify=verify

def growth_decision(g,rows,facts):
    hits=[r for r in rows if r['label']==g['label'].casefold()];decisions=[]
    for r in hits:
        v=re.sub(r'\[S\d+\]','',r['value']);missing=bool(re.search(r'\b(unavailable|not available|not provided|n/?a|cannot calculate)\b',v,re.I))
        nums=re.findall(r'(?<![A-Za-z\d])[+-]?\d[\d,]*(?:\.\d+)?',v)
        if g['value'] is None:ok=missing
        else:ok=not missing and bool(nums) and Decimal(nums[0].replace(',',''))==Decimal(g['value']) and bool(re.search(r'%|\bpercent\b',v,re.I)) and bool(re.fullmatch(r'[+-]?\d[\d,]*\.\d',nums[0]))
        decisions.append(dict(value=v,passed=bool(ok)))
    supported=all(f['passed']for f in facts)
    return {**g,'hits':hits,'observations':decisions,'dependencies_correct':supported,'passed':bool(decisions) and all(d['passed']for d in decisions) and supported}

def rules():
    configure();e.evaluate_rules();tasks={t['id']:t for t in read(P/'tasks.json')};out=[]
    for r in read(P/'rule_results.json'):
        t=tasks[r['task_id']];report=(P/'runs'/r['run_id']/'evaluated_report.md').read_text();rows=e.extract_rows(e.report_body(report))
        facts=[]
        for f in r['facts']:
            precise=f['value'] is None
            if f.get('observed') and f['value'] is not None:
                v=re.sub(r'\[S\d+\]','',f['observed']);m=re.search(r'(?<![A-Za-z\d])[+-]?\d[\d,]*(?:\.\d+)?',v)
                precise=bool(m and re.fullmatch(r'[+-]?\d[\d,]*\.\d{2}',m[0]))
            facts.append({**f,'source_supported':f['passed'],'reference_match':f['passed'],'display_precision_passed':precise})
        derived=[{**f,'supported_calculation':f['passed'],'reference_match':f['passed']}for f in r['derived']]
        growth=[]
        for c,g in zip(t['pair'].split('_'),t['growth']):growth.append(growth_decision(g,rows,[f for f in r['facts']if f['id'].startswith(c+'_')]))
        out.append({**r,'facts':facts,'derived':derived,'growth':growth,'source_numeric_complete':r['numeric_core_passed'],
                    'precision_complete':r['delivered']and all(f['display_precision_passed']for f in facts)})
    save(P/'adjudicated_rule_results.json',out)
    s=read(P/'rule_summary.json');s['planned']=len(read(P/'jobs.json'));save(P/'rule_summary.json',s)

def finalize():
    configure();a.finalize();rs=read(P/'final_results.json');groups={}
    for arm in ARMS:
        rows=[r for r in rs if r['arm']==arm];first=[r for r in rows if r['repetition']==1]
        def counts(items):
            return dict(runs=len(items),growth_correct=sum(g['passed']for r in items for g in r['growth']),growth_requirements=len(items)*2,
                full_required_content_and_constraints=sum(r['combined_completion']and all(d['supported_calculation']for d in r['derived'])and all(g['passed']for g in r['growth'])for r in items),
                narrative_consistency=sum(r['semantic'].get('narrative_consistency',False)for r in items),period_scope=sum(r['semantic'].get('period_scope',False)for r in items))
        repeats=[]
        for tid in sorted({r['task_id']for r in rows if r['repetition']==2}):
            pair=sorted([r for r in rows if r['task_id']==tid],key=lambda r:r['repetition'])
            repeats.append(dict(task_id=tid,outcomes=[dict(repetition=r['repetition'],delivered=r['delivered'],core=r['combined_completion'],growth=all(g['passed']for g in r['growth']),narrative=r['semantic'].get('narrative_consistency'))for r in pair]))
        groups[arm]=dict(all_runs=counts(rows),first_runs=counts(first),prespecified_repeats=repeats)
    save(P/'heldout_summary.json',dict(utc=now(),groups=groups,scope='Eight distinct tasks, two issuer-pair clusters; four tasks repeated per arm. No pooling with earlier development batches.'))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['rules','judge','final']);x=ap.parse_args()
    configure();{'rules':rules,'judge':e.judge,'final':finalize}[x.action]()
