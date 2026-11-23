"""Check manuscript tables directly against sealed reports and preserved modules."""
import hashlib, json, re, sys
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];P=ROOT/'manuscript/v2_3';E=P/'evidence'
BACK=ROOT/'artifacts/manuscript_revision/heldout_14/before'
sys.path[:0]=[str(ROOT),str(ROOT/'src'),str(ROOT/'analysis')]
from experiments.system_comparison import read,save,sha
from close_heldout_14 import metrics,complete
S=ROOT/'artifacts/report_study/heldout_comparison_14'
text=(P/'dissertation_draft_zh.md').read_text();old=(BACK/'dissertation_draft_zh.md').read_text()
def tables(t):
    result={}
    for m in re.finditer(r'^表 (\d+)\. [^\n]+\n\n((?:\|[^\n]+\n)+)',t,re.M):
        result[int(m[1])]=[[c.strip() for c in line.strip('|').split('|')] for line in m[2].splitlines() if not re.fullmatch(r'[|:\s-]+',line)]
    return result
ts=tables(text);oldts=tables(old);assert sorted(ts)==list(range(1,17))
rs=read(S/'final_results.json');checked=[]
groups=[(a,first) for first in (True,False) for a in ('hermes_agent','report_system')]
select=lambda a,f:[r for r in rs if r['arm']==a and(not f or r['repetition']==1)]
for i,key in enumerate(['交付报告','季度金额及对应来源','缺失季度如实披露','请求的业务主题','H2 合计／缺失依赖','原始金额环比／缺失依赖','structure','显式 600 词上限','结构、风格与篇幅同时合规','precision','必需内容、计算与输出约束同时通过'],1):
    expected=[]
    for a,first in groups:
        rows=select(a,first)
        if key in ('structure','precision'):
            n=sum(r['structure_passed'] if key=='structure' else r['precision_complete'] for r in rows);den=len(rows)
        else:
            _,n,den=next(m for m in metrics(rows) if m[0]==key)
        expected.append(f'{n}/{den}')
    assert ts[6][i][1:]==expected,(i,ts[6][i],expected)
    checked.append(dict(table=6,row=i,values=expected))
for i,profile in enumerate(['brief','standard','detailed','missing'],1):
    expected=[]
    for a,first in groups:
        rows=[r for r in select(a,first) if r['profile']==profile]
        expected.append(f'{sum(complete(r) for r in rows)}/{len(rows)}')
    assert ts[7][i][1:]==expected
    checked.append(dict(table=7,row=i,values=expected))
for i,key in enumerate(['cross_source_synthesis','period_scope','requested_depth','narrative_consistency'],1):
    expected=[f'{sum(r["semantic"][key] for r in select(a,first))}/{len(select(a,first))}' for a,first in groups]
    assert ts[8][i][1:]==expected
    checked.append(dict(table=8,row=i,values=expected))
for n in range(9,16):
    assert ts[n]==oldts[n],n
    checked.extend(dict(table=n,row=i,values=row[1:],basis='Preserved previously verified module/functional table') for i,row in enumerate(ts[n][1:],1))
assert len(ts[16])-1==24
assert sum(int(r[2]) for r in ts[16][1:])==64
refs=lambda s:s[s.index('# 参考文献'):s.index('# 附录 A.')]
assert refs(text)==refs(old),'Reference list changed'
assert len(re.findall(r'^!\[',text,re.M))==5
for stale in ['累计覆盖 20 家','56 份季度材料','43.1%','实验收尾时 135']:
    assert stale not in text,stale
for path,digest in read(ROOT/'artifacts/manuscript_revision/heldout_14/protected_files.json').items():
    assert sha(ROOT/path)==digest,path
seal=read(S/'analysis_manifest.json');assert all(sha(S/n)==h for n,h in seal['files'].items())
mapping=read(E/'report_study_integration.json')
for item in mapping['sources'].values():assert sha(ROOT/item['path'])==item['sha256'],item
validation=dict(utc=datetime.now(timezone.utc).isoformat(),scope='Existing v2.3 Chinese; sealed new-issuer Hermes comparison; unchanged module and functional tables',source_sha256=sha(P/'dissertation_draft_zh.md'),table_count=16,figure_count=5,reference_count=20,verified_numeric_rows=checked,cumulative_companies=24,cumulative_quarter_documents=64,main_distinct_tasks=8,main_new_runs=24,all_study_files_unchanged=len(seal['files']),v2_2_unchanged=True,references_unchanged=True,
    prose_review=dict(skill='academic-humanizer',language='zh',scope='Complete supplied manuscript; edits concentrated on5/6 with consistent abstract, implementation, discussion, conclusion and appendices',terminology=['本文报告系统','Hermes 基线','任务完成','正文一致性'],decisions='Lead with implementation and observed advantages; preserve denominator, budget distinction and separate prose results; concentrate scope discussion in7.2; no new external reference claims.'))
save(E/'content_validation.json',validation)
print(json.dumps({'numeric_rows_verified':len(checked),'tables':16,'figures':5,'references':20,'sealed_files':len(seal['files'])}))
