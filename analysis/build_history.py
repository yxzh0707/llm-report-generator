"""Index legacy prototype evidence separately; never use it as formal results."""
import csv
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
rows=[]
for p in sorted((ROOT/'artifacts/phase1').glob('20*')):
 if not p.is_dir() or not (p/'run.json').exists():continue
 run=json.loads((p/'run.json').read_text())
 package=json.loads((p/'prompt_package.json').read_text()) if (p/'prompt_package.json').exists() else {}
 checks=json.loads((p/'checks.json').read_text()) if (p/'checks.json').exists() else {}
 parent=run.get('parent_run_id') or run.get('parent_run') or run.get('source_run')
 rows.append({'run_id':p.name,'purpose':'historical_development_prototype',
  'generation_stage':'revision' if (p/'revision_input.json').exists() else 'first_generation',
  'parent_run_id':parent,'runtime_status':run.get('status','unknown'),
  'automatic_passed':checks.get('mechanical_checks_passed'),
  'chunking_version':package.get('retrieval',{}).get('chunking_version','legacy_pre_parent_child_or_unrecorded'),
  'model_calls':run.get('model_calls'),'embedding_calls':run.get('embedding_calls'),
  'total_tokens':(run.get('usage') or {}).get('total_tokens'),
  'elapsed_seconds':run.get('elapsed_seconds'),'error_type':run.get('error_type'),
  'actual_human_audit_completed':False,
  'record_limit':'Legacy logs may lack usage/finish reason/hash. Assistant manual_review labels are development checks, never independent human audit.'})
out=ROOT/'artifacts/tables';out.mkdir(exist_ok=True)
(out/'phase1_history.json').write_text(json.dumps(rows,indent=2)+'\n')
with (out/'phase1_history.csv').open('w',newline='') as stream:
 writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
(out/'phase1_history_provenance.json').write_text(json.dumps({'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'run_count':len(rows),'formal_results':False},indent=2)+'\n')
print(json.dumps({'historical_phase1_runs':len(rows),'formal_results':False}))
