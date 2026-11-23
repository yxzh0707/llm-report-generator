"""Recover observed failed-run usage; document native Hermes closeout accounting."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];P=ROOT/'artifacts/report_study/system_repair_04'
rows=json.loads((P/'adjudicated_rule_results.json').read_text());audit=[]
for row in rows:
    folder=P/'runs'/row['run_id']
    if row['arm']=='report_system':
        events=[json.loads(s) for s in (folder/'trajectory.jsonl').read_text().splitlines()]
        completed=[e for e in events if e['type']=='model_completed']
        usages=[e['data'].get('usage') for e in completed]
        if all(u and u.get('total_tokens') is not None for u in usages):
            observed=sum(u['total_tokens'] for u in usages)
            existing=(row.get('usage') or {}).get('total_tokens')
            if existing is not None:assert existing==observed,(row['run_id'],existing,observed)
            else:
                row['usage']={'total_tokens':observed,'provenance':'Sum of every observed model_completed event; native terminal failure omitted aggregate usage.'}
                audit.append(dict(run_id=row['run_id'],kind='recovered_observed_usage',model_responses=len(usages),total_tokens=observed,
                    trajectory_sha256=hashlib.sha256((folder/'trajectory.jsonl').read_bytes()).hexdigest()))
    else:
        output=json.loads((folder/'hermes_output.json').read_text())
        saved=folder/'workspace/work/outputs/final_report.md'
        if saved.exists():assert saved.read_text()==(folder/'evaluated_report.md').read_text()
        messages=output.get('messages',[])
        tool_calls=sum(len(m.get('tool_calls',[])) for m in messages)
        extra=output.get('turn_exit_reason','').startswith('max_iterations_reached')
        audit.append(dict(run_id=row['run_id'],kind='native_hermes_accounting',native_completed=output.get('completed'),
            native_turn_exit_reason=output.get('turn_exit_reason'),loop_calls=output.get('api_calls'),tool_calls=tool_calls,
            evaluated_report_from_saved_file=saved.exists(),
            unmetered_closeout_possible=extra,
            note='Native iteration-limit summary bypasses main-loop request overrides and token aggregation. It is toolless and did not write the evaluated report. Treat Hermes token totals as recorded loop usage, not verified total billing.' if extra else 'Normal loop completion.'))
(P/'adjudicated_rule_results.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
(P/'telemetry_audit.json').write_text(json.dumps({'records':audit,'comparison_scope':'Same Qwen endpoint/model for report generation; native budget and tool policies are documented separately. No exact end-to-end token-saving percentage is claimed.'},ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'recovered':[a for a in audit if a['kind']=='recovered_observed_usage'],
    'hermes_iteration_limit_runs':sum(a.get('unmetered_closeout_possible',False) for a in audit)},ensure_ascii=False))
