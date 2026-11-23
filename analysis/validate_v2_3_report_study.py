"""Cross-check manuscript table cells against sealed experiment summaries."""
from pathlib import Path
import json
import hashlib
import re
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
M = ROOT/'manuscript/v2_3'
STUDY = ROOT/'artifacts/report_study'
text = (M/'dissertation_draft_zh.md').read_text()
def read(name, file='summary.json'):
    return json.loads((STUDY/name/file).read_text())
def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()
tables = {}
for match in re.finditer(r'^表 (\d+)\. [^\n]+\n\n((?:\|[^\n]+\n)+)',text,re.M):
    rows = [list(map(str.strip,line.strip('|').split('|'))) for line in match[2].splitlines()]
    tables[int(match[1])] = [r for r in rows[2:]]
actual_tables=tables.copy()
mapping_file=M/'evidence/system_comparison_integration.json'
mapping=json.loads(mapping_file.read_text())['table_mapping'] if mapping_file.exists() else {f'OLD{i}':i for i in range(1,13)}
expected_tables=16 if 'SYS' in mapping else 12
assert sorted(actual_tables)==list(range(1,expected_tables+1))
tables={i:actual_tables[mapping[f'OLD{i}']] for i in range(1,13)}
checks=[]
def cells(table, row, expected):
    assert tables[table][row][1:] == expected, (table,row,tables[table][row],expected)
    checks.append({'table':mapping[f'OLD{table}'],'row':row+1,'verified_values':expected})

main=read('main_comparison_01')['groups']
order=['prompt_only','tool_checked']
for row,key,denom in [(0,'delivered','reports'),(1,'task_complete','reports'),(2,'available_correct','available_items'),(5,'honest_abstentions','missing_items')]:
    cells(5,row,[f'{main[a][key]}/{main[a][denom]}' for a in order])
dec=read('main_comparison_01','decisions.json')
for row,ids in [(3,{'AQ3','AQ4','BQ3','BQ4'}),(4,{'AH2','BH2','AGROWTH','BGROWTH','GAP'})]:
    expected=[]
    for arm in order:
        relevant=[v for r in dec if r['arm']==arm for v in r['decisions'] if (v['id'] in {'AQ3','AQ4','BQ3','BQ4'}) == (row==3) and v['available']]
        expected.append(f"{sum(v['completed'] for v in relevant)}/{len(relevant)}")
    cells(5,row,expected)
for row,key,fmt in [(8,'reported_total_tokens',','),(9,'mean_model_calls','.2f'),(10,'mean_seconds','.2f')]:
    cells(5,row,[format(main[a][key],fmt) for a in order])
structure,length={},{}
for a in order:
    audits=[json.loads((STUDY/'main_comparison_01/runs'/r['run_id']/'audit.json').read_text()) for r in dec if r['arm']==a]
    passed=sum(not x['automatic']['missing_headings'] and not x['automatic']['wrong_heading_levels'] and x['automatic']['section_order_correct'] for x in audits)
    structure[a]=f'{passed}/{len(audits)}'
    applicable=[v for x in audits for v in x['customization']['items'] if v['id']=='depth_words']
    length[a]=f"{sum(v['passed'] for v in applicable)}/{len(applicable)}"
cells(5,6,[structure[a] for a in order]);cells(5,7,[length[a] for a in order])

hybrid=read('hybrid_02')['aggregate']
for i,a in enumerate(['upload_early','web_late','hybrid','all_uploaded']):
    g=hybrid[a]
    assert tables[6][i][2:]==[f"{g['completed']}/{g['requirements']}",f"{g['complete_reports']}/{g['reports']}"]
    checks.append({'table':mapping['OLD6'],'row':i+1,'verified_values':tables[6][i][2:]})
custom=read('customization_01')['groups']
for i,a in enumerate(['standard_brief','standard_detailed','comparison_brief','comparison_detailed']):
    g=custom[a]
    cells(7,i,[str(g['reports']),f"{g['correct_structure']}/{g['reports']}",f"{g['completed_items']}/{g['requested_items']}",str(g['mean_body_words'])])
web=read('web_period_01')['groups']
for row,key,denom in [(0,'web_pages',None),(1,'wrong_year_admitted',None),(2,'grounded_items_completed','available_requirements'),(3,'correct_abstentions','absent_requirements'),(4,'complete_reports','reports'),(5,'total_tokens',None)]:
    cells(8,row,[f'{web[a][key]}/{web[a][denom]}' if denom else (f'{web[a][key]:,}' if row==5 else str(web[a][key])) for a in ['off','enforce']])
financial=read('financial_period_01')['groups']
for row,key,denom in [(0,'completed_items','requested_items'),(1,'complete','reports'),(2,'reported_tokens',None)]:
    cells(9,row,[f'{financial[a][key]}/{financial[a][denom]}' if denom else f'{financial[a][key]:,}' for a in ['legacy12','wide100','filtered100']])
workspace=read('full_original_02')['groups']
for row,key in enumerate(['delivered','value_correct','strict_correct','complete']):
    cells(10,row,[f"{workspace[a][key]}/{workspace[a]['reports' if row in (0,3) else 'facts']}" for a in ['prefix','worker_workspace','full_original']])
terminal=read('terminal_reliability_02','results.json')['cases']
assert len(terminal)==11 and all(x['passed'] for x in terminal)
inventory=read('cross_company_01','cumulative_inventory.json')
assert len(inventory['documents'])==56 and len({d['company'] for d in inventory['documents']})==20
assert sum(int(r[2]) for r in tables[12])==56
assert list(map(int,re.findall(r'^\[(\d+)\]',text,re.M)))==list(range(1,21))
body=text.split('# 参考文献')[0]
assert set(map(int,re.findall(r'\[(\d+)\]',body)))==set(range(1,21))
assert list(map(int,re.findall(r'^图 (\d+)\.',text,re.M)))==list(range(1,6 if 'SYS' in mapping else 5))
for img in re.findall(r'!\[.*?\]\((.*?)\)',text):assert (M/img).exists()
assert '[S#]' in text and '250–500' not in text


if 'SYS' in mapping:
    new=read('system_comparison_02','final_summary.json');assert new['completed_runs']==64 and new['unresolved']==0
    g=new['groups'];order=['general_agent','report_system']
    def newcells(key,row,expected):
        observed=actual_tables[mapping[key]][row][1:]
        assert observed==expected,(key,row,observed,expected)
        checks.append({'table':mapping[key],'row':row+1,'verified_values':expected})
    for i,(key,denom) in enumerate([('delivered',32),('quarter_facts_supported',120),('missing_correct',8),('business_topics_passed',64),('structure_passed',32),('word_limit_passed',16),('format_passed',32),('precision_complete',32),('combined_completion',32),('derived_correct',64)]):
        newcells('SYS',i,[f'{g[a][key]}/{denom}' for a in order])
    for row,key,fmt in [(10,'tokens',','),(11,'mean_calls','.2f'),(12,'mean_seconds','.2f')]:newcells('SYS',row,[format(g[a][key],fmt) for a in order])
    for row,profile in enumerate(['brief','standard','detailed','missing']):
        newcells('PROFILE',row,[f"{g[a]['profiles'][profile][key]}/8" for key in ['content_complete','format_passed'] for a in order])
    for row,key in enumerate(['cross_source_synthesis','period_scope','requested_depth','narrative_consistency']):newcells('SEM',row,[f"{g[a]['semantic'][key]}/32" for a in order])
    assert '简化生成流程' not in text and '14 个期间暂不能确认' not in text
    for path,expected in read('system_comparison_02','analysis_manifest.json')['files'].items():assert sha(STUDY/'system_comparison_02'/path)==expected,path
    assert '43.1%' in text
    audit=read('web_period_01','source_review.json');ds=read('web_period_01','source_decisions.json')
    ids={d['document_id'] for d in ds if d['decision']=='quarantine'}
    from collections import Counter
    assert Counter(d['role'] for d in audit['documents'] if d['document_id'] in ids)=={'index_page':8,'event_page':2,'preannouncement':1,'supporting_statement':3}

# Ensure the source artifacts referenced by the new manuscript remain sealed.
integration=json.loads((M/'evidence/report_study_integration.json').read_text())
assert integration['sha256']==sha(M/'dissertation_draft_zh.md')
for s in integration['sources'].values():assert sha(ROOT/s['path'])==s['sha256']
closure=read('closure_01','verification.json')
sealed=[]
for item in closure['prior_sealed_studies']:
    folder=STUDY/item['study']; mp=folder/'analysis_manifest.json'
    assert sha(mp)==item['manifest_sha256'],item['study']
    manifest=json.loads(mp.read_text())
    for path,expected in manifest['files'].items():
        assert sha(folder/path)==expected,(item['study'],path)
    sealed.append({'study':item['study'],'files':len(manifest['files'])})
result={'utc':datetime.now(timezone.utc).isoformat(),'scope':'Chinese v2.3;64-run ordinary Agent comparison added; previous source experiments unchanged','source_sha256':sha(M/'dissertation_draft_zh.md'),'table_count':expected_tables,'figure_count':5 if 'SYS' in mapping else 4,'reference_count':20,'verified_numeric_rows':checks,'inventory':{'companies':20,'quarterly_documents':56},'sealed_studies_verified':sealed,'language_audit':{'skill':'academic-humanizer','scope':'whole Chinese manuscript','preserved':'claims, denominators, terminology and historical results','changes':'contribution-led organization; consolidated limitations; explicit metric definitions; removed repetitive defensive and inflated phrasing'}}
target=M/'evidence/content_validation.json'
backup=ROOT/'artifacts/manuscript_revision/v2_3_20261027/before/content_validation.json'
if target.exists() and not backup.exists():backup.write_bytes(target.read_bytes())
target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'tables':expected_tables,'figures':5 if 'SYS' in mapping else 4,'references':20,'numeric_rows_verified':len(checks),'sealed_studies_verified':len(sealed)},ensure_ascii=False))
