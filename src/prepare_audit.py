"""Create a directly reviewable source-support package, without grading it."""
import argparse
import json
from pathlib import Path
import re
import pysbd
from provenance import write_json, digest


def prepare(run_dir):
    run_dir = Path(run_dir)
    manifest = json.loads((run_dir/'run_manifest.json').read_text())
    report = (run_dir/'raw_report.md').read_text()
    sources = json.loads((run_dir/'evidence_ledger.json').read_text())
    by_id = {s['citation']:s for s in sources}
    body = re.split(r'^#{1,2}[ \t]+Sources[ \t]*$',report,maxsplit=1,flags=re.M)[0]
    candidates=[]
    for para in re.split(r'\n\s*\n',body):
        if not para.strip() or para.strip().startswith('#'):
            continue
        for claim in pysbd.Segmenter(language='en',clean=False).segment(para):
            if not re.search(r'\d|reported|revenue|segment|platform|business',claim,re.I):
                continue
            ids = list(dict.fromkeys(re.findall(r'\[S\d+\]',claim)))
            evidence=[]
            for identity in ids:
                s=by_id.get(identity)
                if s:
                    assert len(s['text']) == s['char_end']-s['char_start']
                    evidence.append({k:s.get(k) for k in ['citation','source_kind','document_id','source_url',
                        'chunk_id','char_start','char_end','text_sha256','excerpt_sha256','text']})
            candidates.append({'id':f'C{len(candidates)+1}','exact_claim':claim.strip(),
                'citation_ids':ids,'evidence':evidence,'selection_confirmed_by_actual_reviewer':False,
                'judgment':None,'reason':None,'actual_reviewer':None})
            if len(candidates)==5: break
        if len(candidates)==5:break
    out=run_dir/'human_review';out.mkdir(exist_ok=True)
    package={'run_id':run_dir.name,'purpose':manifest.get('purpose'),
        'raw_report_sha256':digest(report.encode()),'status':'awaiting_actual_human_review',
        'selection':'automatically proposed first five material sentences; actual reviewer confirms importance and selection',
        'actual_reviewer':None,'source_support_labels':['supported','contradicted','insufficient'],
        'items':candidates,'completed':False,'assistant_grades':None}
    write_json(out/'review.json',package)
    lines=[f'# Source-support review: {run_dir.name}', '',
        f"Purpose: {manifest.get('purpose')}. Actual human review pending; these are ungraded proposed items.",
        'Confirm the five selected facts, inspect the linked excerpts, then fill judgment, reason and actual reviewer in review.json.', '']
    for row in candidates:
        lines += [f"## {row['id']}", '', '> '+row['exact_claim'].replace('\n','\n> '), '',
                  'Judgment: ___ (supported / contradicted / insufficient). Reason: ___. Actual reviewer: ___.', '']
        for s in row['evidence']:
            lines += [f"### {s['citation']} — {s['document_id']}", '',
                      f"Source kind: {s['source_kind']}; normalized characters [{s['char_start']}, {s['char_end']}).", '',
                      '```text',s['text'],'```','']
        if not row['evidence']: lines += ['No recognized citation in this proposed claim.','']
    (out/'review.md').write_text('\n'.join(lines)+'\n')
    return out


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('run_dir',type=Path)
    print(prepare(p.parse_args().run_dir))
