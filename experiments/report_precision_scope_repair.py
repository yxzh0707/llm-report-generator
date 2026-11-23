"""Targeted confirmation of a newly discovered operation-scope precision defect.

One original Broadcom/Qualcomm draft. Separate from all four-case batch scores.
"""
import argparse,asyncio,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from experiments import report_semantic_repair as base
from experiments.system_comparison import read,save,sha,now
base.P=ROOT/'artifacts/report_study/precision_scope_13';P=base.P

def prepare():
    base.prepare();jobs=[j for j in read(P/'jobs.json') if j['task_id']=='broadcom_qualcomm_detailed'];save(P/'jobs.json',jobs)
    p=read(P/'protocol.json');p.update(type='single-case precision-scope confirmation',
        previous_batch='semantic_repair_12',previous_outcome='All four delivered, but the additional sequential percentage used rounded monetary inputs: 7.1 rather than 7.0 at one decimal.',
        change='A displayed-quarter sum rounds its own operands only; unrelated growth calculations retain raw precision, including shared fact IDs.',
        repair_cases={'broadcom_qualcomm_detailed':'narrative_growth_basis'},
        acceptance='Report correct comparison basis; any added Automotive QoQ is 7.0 percent at one decimal from original 984 and 1053 million. Preserve requested facts and business topics.',
        selection='One follow-up of the newly exposed calculation-scope defect; never pooled with batch 12 as a fresh four-case result.')
    save(P/'protocol.json',p);f=read(P/'freeze.json')
    for name in ['jobs.json','protocol.json']:f['files'][name]=sha(P/name)
    save(P/'freeze.json',f)

async def run():
    from runtime_config import load_project_environment
    load_project_environment();base.verify();assert not(P/'execution.json').exists()
    save(P/'execution.json',dict(started_utc=now(),workers=1))
    await base.replay(read(P/'jobs.json')[0]);base.verify()
    save(P/'execution_complete.json',dict(completed_utc=now(),new_model_runs=1))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['prepare','verify','run','rules']);a=ap.parse_args()
    if a.action=='prepare':prepare()
    elif a.action=='run':asyncio.run(run())
    else:getattr(base,a.action)()
