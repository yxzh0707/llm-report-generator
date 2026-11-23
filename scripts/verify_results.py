#!/usr/bin/env python3
"""Recompute reported counts from saved decisions, without model or network calls.

This verifies aggregation and file identity, not semantic truth of adjudications.
"""
import argparse, csv, hashlib, json
from pathlib import Path

BASE=Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--reference-root',type=Path,help='Read full final_results.json in a reference project')
ap.add_argument('--check-manifest',action='store_true')
ap.add_argument('--output',type=Path)
args=ap.parse_args()
def read(p):return json.loads(p.read_text(encoding='utf-8'))
if args.check_manifest:
    manifest=read(BASE/'MANIFEST.sha256.json')
    bad=[n for n,h in manifest.items() if not(BASE/n).is_file() or hashlib.sha256((BASE/n).read_bytes()).hexdigest()!=h]
    if bad:raise SystemExit('Hash mismatch or missing: '+', '.join(bad[:8]))
    print(f'OK: {len(manifest)} packaged files match their manifest')
if args.reference_root:
    full=read(args.reference_root/'artifacts/report_study/heldout_comparison_14/final_results.json')
    rows=[]
    for r in full:
        lens=[x for x in r['customization']['items'] if x['id']=='depth_words']
        rows.append(dict(run_id=r['run_id'],arm=r['arm'],task_id=r['task_id'],repetition=r['repetition'],
          delivered=bool(r['delivered']),recorded_core=bool(r['combined_completion']),
          totals=[bool(x['supported_calculation']) for x in r['derived']],
          growth=[bool(x['passed']) for x in r['growth']],
          facts=[bool(x['source_supported']) for x in r['facts'] if x['value'] is not None],
          missing=[bool(x['source_supported']) for x in r['facts'] if x['value'] is None],
          length=[bool(x['passed']) for x in lens],narrative=bool(r['semantic']['narrative_consistency']),
          report_sha256=r['report_sha256']))
else:rows=read(BASE/'results/main_run_decisions.json')
assert len(rows)==24 and len({r['run_id'] for r in rows})==24
assert len({r['task_id'] for r in rows})==8
def fraction(a):return f'{sum(a)}/{len(a)}'
records=[]
for first in [True,False]:
 for arm in ['report_system','hermes_agent']:
    rs=[r for r in rows if r['arm']==arm and (not first or r['repetition']==1)]
    records.append({'scope':'first_runs' if first else 'all_prespecified_runs','arm':arm,
      'required_content_and_constraints':fraction([r['recorded_core'] and all(r['totals']) and all(r['growth']) for r in rs]),
      'quarterly_facts_and_sources':fraction([x for r in rs for x in r['facts']]),
      'totals_and_missing_dependencies':fraction([x for r in rs for x in r['totals']]),
      'raw_growth_and_missing_dependencies':fraction([x for r in rs for x in r['growth']]),
      'explicit_word_limit':fraction([x for r in rs for x in r['length']]),
      'no_major_narrative_contradictions':fraction([r['narrative'] for r in rs])})
expected=read(BASE/'results/main_expected_counts.json')
assert records==expected,'Rebuilt table differs from expected counts'
if args.reference_root:
    study=args.reference_root/'artifacts/report_study/heldout_comparison_14'
    for r in rows:
        p=study/'runs'/r['run_id']/'evaluated_report.md'
        assert hashlib.sha256(p.read_bytes()).hexdigest()==r['report_sha256'],p
    print('OK: all 24 evaluated reports match recorded hashes')
if args.output:
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
for row in records:print(json.dumps(row,ensure_ascii=False))
print('OK: main-result aggregation matches. No model calls were made.')
