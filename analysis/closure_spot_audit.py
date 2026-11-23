"""Prepare the fixed assistant-only source check; no automatic grading."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import pysbd

CONDITIONS = ('T2_uploaded_only','T4_uploaded_only','T5_web_only','T6_hybrid')


def prepare(out):
    dest=out/'assistant_spot_audit'
    dest.mkdir(exist_ok=True)
    for cid in CONDITIONS:
        for arm in ('direct','system'):
            jid=f'{cid}_r1_{arm}';run=out/'runs'/jid
            if not (run/'result.json').exists():continue
            target=dest/(jid+'.json')
            if target.exists():continue
            report=(run/'final_report.md').read_text()
            body=re.split(r'^#{1,6} Sources\s*$',report,maxsplit=1,flags=re.M)[0]
            claims=[]
            for para in re.split(r'\n\s*\n',body):
                if not para.strip() or para.strip().startswith('#'):continue
                for claim in pysbd.Segmenter(language='en',clean=False).segment(para):
                    if not re.search(r'\d|reported|revenue|segment|platform|business',claim,re.I):continue
                    claims.append({'id':f'C{len(claims)+1}','claim':claim.strip(),'judgment':None,'reason_zh':None})
                    if len(claims)==5:break
                if len(claims)==5:break
            packet={'run_id':jid,'stage':'final','reviewer':'current Codex assistant, not human; no prior judge labels supplied',
                'selection':'fixed four conditions, both arms, repetition 1; first five candidate factual sentences using the historical selector heuristic',
                'report_sha256':hashlib.sha256(report.encode()).hexdigest(),'sources_path':str((run/'sources.json').relative_to(out)),
                'evidence_scope':'all returned excerpts for this run; task wording alone does not support a factual premise',
                'items':claims,'completed':False}
            target.write_text(json.dumps(packet,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'prepared':len(list(dest.glob('*.json')))}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();prepare(a.out)
