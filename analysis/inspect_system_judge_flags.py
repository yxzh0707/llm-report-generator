import sys,json,re,difflib
from pathlib import Path
P=Path('artifacts/report_study/system_comparison_02')
s=json.loads((P/'final_summary.json').read_text()); prefix=sys.argv[1]
for u in s['unresolved_items']:
 n,k=u['run_id'],u['criterion']
 if not n.startswith(prefix):continue
 j=json.loads((P/'judge'/n/'validated.json').read_text()); row=next(x for x in j['results'] if x['id']==k)
 print('\n',n,k,'passed',row['passed']);print('reason:',row['reason'])
 report=(P/'runs'/n/'evaluated_report.md').read_text();ledger={x['citation']:x['text'] for x in json.loads((P/'runs'/n/'evidence_ledger.json').read_text())}
 for f in j['quote_flags']:
  if f['criterion']!=k:continue
  q=f['quote'];txt=report if f['kind']=='report_quote' else ledger[q['citation']];q=q if isinstance(q,str) else q['quote']
  chunks=re.split(r'\n\s*\n|(?<=[.!?])\s+(?=[A-Z])',txt)
  norm=lambda t:re.sub(r'[^a-z0-9 ]','',t.casefold())
  best=sorted(chunks,key=lambda x:difflib.SequenceMatcher(None,norm(q),norm(x)).ratio(),reverse=True)[:1]
  print('FLAG',f['kind'],q);print('ACTUAL',best[0][:1600])
