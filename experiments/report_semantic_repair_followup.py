"""Repeat the complete four-case repair protocol after fixing repair accounting.

Keep semantic_repair_11 intact (three deliveries, one bounded calculation failure).
No selective replacement: this batch reports all four new outcomes together.
"""
import argparse,asyncio,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from experiments import report_semantic_repair as base
from experiments.system_comparison import read,save,sha
base.P=ROOT/'artifacts/report_study/semantic_repair_12';P=base.P

def prepare():
    base.prepare();p=read(P/'protocol.json')
    p.update(previous_batch='semantic_repair_11',previous_outcome='Three of four repaired; one terminated after two new incomplete calculator plans plus one previous successful call.',
        change='Allow three consecutive rejected calculation plans; successful calculations do not consume a later repair chain. The total budget remains 16 model and 24 tool calls.',
        selection='All four original failure drafts are replayed at this single fixed version; no pooling with batch 11.')
    save(P/'protocol.json',p);f=read(P/'freeze.json');f['files']['protocol.json']=sha(P/'protocol.json');save(P/'freeze.json',f)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['prepare','verify','run','rules']);a=ap.parse_args()
    if a.action=='prepare':prepare()
    elif a.action=='run':asyncio.run(base.run())
    else:getattr(base,a.action)()
