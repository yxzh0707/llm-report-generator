"""Verify all frozen runs and their final independent decisions, then seal them."""
import sys,json,re,hashlib,shutil
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from experiments.system_comparison import verify,P,read,sha,save
verify();jobs=read(P/'jobs.json');rules=read(P/'final_results.json');summary=read(P/'final_summary.json')
assert len(jobs)==len(rules)==64 and summary['unresolved']==0
assert {x['run_id'] for x in jobs}=={x['run_id'] for x in rules}
assert all(len(x['semantic'])==6 for x in rules)
for r in rules:
 folder=P/'runs'/r['run_id'];manifest=read(folder/'run_manifest.json');assert manifest['status']!='started'
 assert sha(folder/'evaluated_report.md')==r['report_sha256']
 assert (P/'judge'/r['run_id']/'validated.json').exists()
 assert r['usage']['total_tokens'] is not None
for key in ('general_agent','report_system'):
 a=[r for r in rules if r['arm']==key];g=summary['groups'][key]
 assert len(a)==32 and all(sum(r['profile']==p for r in a)==8 for p in ['brief','standard','detailed','missing'])
 assert g['tokens']==sum(r['usage']['total_tokens'] for r in a)
# Check recorded audit quotations against the actual outputs and full sources.
for e in read(P/'semantic_adjudications.json'):
 folder=P/'runs'/e['run_id'];t=(folder/'evaluated_report.md').read_text(); norm=lambda x:re.sub(r'\s+',' ',x).strip()
 for q in e.get('report_quotes',[])+([e['report_quote']] if e.get('report_quote') else []):assert norm(q) in norm(t),(e['run_id'],e['criterion'])
 led={x['citation']:x['text'] for x in read(folder/'evidence_ledger.json')}
 for q in e.get('source_context',[]):assert q['actual_verbatim_span'] in led[q['citation']]
assert len(read(P/'assistant_sample_audit.json')['records'])==16
empty=[r['run_id'] for r in rules if not r['delivered']];assert len(empty)==2
assert all(not any(r['semantic'].values()) for r in rules if not r['delivered'])
stub=next(r for r in rules if r['run_id']=='broadcom_qualcomm_standard_report_system_1');assert stub['delivered'] and not stub['business_complete'] and not any(stub['semantic'].values())
code=P/'analysis_code';code.mkdir(exist_ok=True)
for n in ['evaluate_system_comparison.py','adjudicate_system_comparison.py','normalize_system_judge_quotes.py','record_system_semantic_audit.py','seal_system_comparison.py']:
 shutil.copyfile(ROOT/'analysis'/n,code/n)
verification={'utc':datetime.now(timezone.utc).isoformat(),'frozen_generation_verified':True,'planned_runs':64,'completed_runs':64,'same_model':'Qwen3.8-27B','source_documents':16,'companies':8,'judge_runs':64,'unresolved_criteria':0,'assistant_sample_reports':16,'empty_reports_retained':empty,'placeholder_report_failed_content':stub['run_id'],'adjudications':len(read(P/'semantic_adjudications.json')),'evaluation_note':'Raw frozen reference matches preserved. Source-disclosed alternatives, equivalent result extraction, precision and quote audits applied to both arms. No regeneration or prompt changes. Assistant audit is not independent human assessment.','groups':summary['groups']}
save(P/'verification.json',verification)
exclude={'analysis_manifest.json','latest_rule_summary.log','latest_final_summary.log'}
files={str(f.relative_to(P)):sha(f) for f in sorted(P.rglob('*')) if f.is_file() and f.name not in exclude and not f.name.startswith('manuscript_') and '__pycache__' not in f.parts and f.suffix!='.log'}
save(P/'analysis_manifest.json',{'utc':verification['utc'],'files':files,'scope':'All frozen input/run/evaluation artifacts and evaluation code snapshots; manuscript drafts and transient logs excluded.'})
print(json.dumps({'runs':64,'files_sealed':len(files),'unresolved':0,'empty_reports':len(empty)}))
