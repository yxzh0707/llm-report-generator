"""Explicit post-hoc heading-only diagnostic; primary scores remain unchanged."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from experiments.closure_study import read,save,sha,audit,required_headings,verify


def run(out):
    verify(out);dest=out/'format_diagnostic';dest.mkdir(exist_ok=True)
    save(dest/'protocol.json',{'classification':'post-hoc diagnostic prompted by observed H1 instead of H2 failures',
        'created_at':datetime.now(timezone.utc).isoformat(),
        'operation':'for main initial reports in both arms, replace only heading prefix for exactly matching required titles with ##; retain text, order, duplicate titles and citations',
        'new_model_calls':0,'primary_scores_unchanged':True})
    results=[]
    for j in read(out/'plan.json'):
        if j['group']!='main':continue
        d=out/'runs'/j['id'];r=read(d/'result.json');report=(d/'initial/raw_report.md').read_text()
        heads=set(required_headings(j['request']['structure']))
        def replace(m):
            return '## '+m.group(2) if m.group(2).strip() in heads else m.group(0)
        normalized=re.sub(r'^(#{1,6})[ \t]+([^\n]+?)\s*$',replace,report,flags=re.M)
        # No body text edit: heading-marker-stripped token sequences must be equal.
        strip=lambda text:re.findall(r'\S+',re.sub(r'^#{1,6}[ \t]+','',text,flags=re.M))
        assert strip(report)==strip(normalized)
        target=dest/'reports'/j['id'];target.mkdir(parents=True,exist_ok=True)
        (target/'heading_normalized.md').write_text(normalized)
        a=audit(normalized,j['request'],read(d/'sources.json'),j['documents'],r['initial'].get('finish_reason','error'))
        assert a['body_words']==r['initial']['audit']['body_words']
        results.append({'id':j['id'],'arm':j['arm'],'original_pass':r['initial']['audit']['automatic_passed'],
            'normalized_pass':a['automatic_passed'],'original_sha256':sha(report.encode()),
            'normalized_sha256':sha(normalized.encode()),'audit':a})
    summary={arm:{'planned':sum(r['arm']==arm for r in results),
        'original_pass':sum(r['original_pass'] for r in results if r['arm']==arm),
        'heading_normalized_pass':sum(r['normalized_pass'] for r in results if r['arm']==arm)} for arm in ('direct','system')}
    save(dest/'summary.json',{'groups':summary,'runs':results,'interpretation':'exploratory deterministic formatting adjustment, not the frozen primary outcome'})
    print(json.dumps(summary))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.out.resolve())
