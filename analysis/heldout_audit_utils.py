"""Persist source-audit decisions with checked, contiguous evidence quotations."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from experiments.system_comparison import read,save,norm,sha,now
P=ROOT/'artifacts/report_study/heldout_comparison_14'

def add(run_id,criterion,passed,reason,report_quotes=(),source_quotes=()):
    folder=P/'runs'/run_id;report=norm((folder/'evaluated_report.md').read_text());sources={s['citation']:norm(s['text'])for s in read(folder/'evidence_ledger.json')}
    for quote in report_quotes:assert norm(quote) in report,quote
    for cite,quote in source_quotes:assert norm(quote) in sources[cite],(cite,quote)
    path=P/'semantic_adjudications.json';rows=read(path)if path.exists()else[]
    rows=[r for r in rows if(r['run_id'],r['criterion'])!=(run_id,criterion)]
    rows.append(dict(run_id=run_id,criterion=criterion,passed=passed,reviewer='assistant_source_audit',reason=reason,
        report_quotes=list(report_quotes),source_quotes=[dict(citation=c,quote=q)for c,q in source_quotes],report_sha256=sha(folder/'evaluated_report.md')))
    save(path,rows)

def reviewed(run_id,notes='Read complete report; no additional material source/period/ratio inconsistency found beyond recorded adjudications.'):
    path=P/'reviewed_reports.json';rows=read(path)if path.exists()else[]
    assert not any(r['run_id']==run_id for r in rows),run_id
    rows.append(dict(run_id=run_id,utc=now(),report_sha256=sha(P/'runs'/run_id/'evaluated_report.md'),notes=notes))
    save(path,rows)
