"""Derive a portable single-run request without modifying a frozen input."""
import argparse
import hashlib
import json
from pathlib import Path


def prepare(freeze,cell,output):
    freeze=Path(freeze).resolve()
    plan=json.loads((freeze/'run_plan.json').read_text())
    cfg=next(c for c in plan if f"{c['condition_id']}_r{c['repetition']}"==cell)
    packet=freeze/Path(cfg['frozen_evidence_file']).name
    if hashlib.sha256(packet.read_bytes()).hexdigest()!=cfg['frozen_evidence_sha256']:
        raise ValueError('Evidence hash mismatch')
    root=Path(__file__).resolve().parents[1]
    run=root/'artifacts/runs'/(freeze.name+'_'+cell+'_a001')
    replay={**cfg,'purpose':'reproduction','frozen_evidence_file':str(packet),
            'corpus_root':str(run/'inputs'),'replay_of':run.name}
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(replay,indent=2)+'\n')
    print(output)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--freeze',required=True,type=Path)
    parser.add_argument('--cell',required=True);parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();prepare(args.freeze,args.cell,args.output)
