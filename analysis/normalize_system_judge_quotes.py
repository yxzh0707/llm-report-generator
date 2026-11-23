"""Resolve only lexical quote formatting; leave semantic paraphrases for audit."""
import json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'src'),str(ROOT/'analysis')]
from experiments.system_comparison import P,read,save
from evaluate_system_comparison import RUBRIC

def tokens(text):
    # Token offsets remain in original text. Decimal punctuation is meaningful.
    return [(m.group().casefold().replace(',',''),m.start(),m.end()) for m in re.finditer(r'\d[\d,]*(?:\.\d+)?|[A-Za-z]+|[%$]',text)]

def actual_quote(quote,text):
    q=[v[0] for v in tokens(quote)];t=tokens(text)
    if not q:return None
    for i in range(len(t)-len(q)+1):
        if [x[0] for x in t[i:i+len(q)]]==q:return text[t[i][1]:t[i+len(q)-1][2]]
    return None

edits=read(P/'semantic_adjudications.json') if(P/'semantic_adjudications.json').exists() else []
done={(x['run_id'],x['criterion']) for x in edits};added=0
for p in sorted((P/'judge').glob('*/validated.json')):
    j=read(p);name=p.parent.name;report=(P/'runs'/name/'evaluated_report.md').read_text()
    ledger={s['citation']:s['text'] for s in read(P/'runs'/name/'evidence_ledger.json')}
    if not report.strip():
        for key in RUBRIC:
            if(name,key) not in done:
                edits.append(dict(run_id=name,criterion=key,passed=False,reviewer='deterministic_empty_report_check',report_quote='',reason='No report was delivered. A judge-generated quotation cannot establish content in an empty report.'));added+=1
        continue
    for key in sorted({x['criterion'] for x in j.get('quote_flags',[])}):
        if(name,key) in done:continue
        resolved=[]
        for flag in j['quote_flags']:
            if flag['criterion']!=key:continue
            kind=flag['kind'];q=flag.get('quote','')
            if kind=='report_quote':found=actual_quote(q,report)
            elif kind=='source_quote':found=actual_quote(q['quote'],ledger.get(q['citation'],''))
            else:found=None
            if found is None:break
            resolved.append({'kind':kind,'original_quote':q,'actual_verbatim_span':found})
        else:
            row=next(x for x in j['results'] if x['id']==key)
            edits.append(dict(run_id=name,criterion=key,passed=row['passed'],reviewer='lexical_quote_validation',resolved_quotes=resolved,reason='All flagged quotations match contiguous original token sequences after removing Markdown emphasis, punctuation spacing and table dot leaders. Values, words and order unchanged. Original model judgment retained.'));added+=1
save(P/'semantic_adjudications.json',edits);print('Resolved',added,'formatting/empty-report cases; total',len(edits))
