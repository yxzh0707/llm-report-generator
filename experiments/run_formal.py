"""Execute exactly the frozen 21+3 cells, serially, preserving every attempt."""
import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from provenance import digest,source_version,write_json
from run_report import run


def verify_freeze(freeze):
    m=json.loads((freeze/'freeze_manifest.json').read_text())
    if m['status']!='frozen':raise ValueError('Experiment has not been finalized')
    if source_version(ROOT)['sha256']!=m['code_sha256']:raise ValueError('Code changed after freeze')
    for name,sha in m['files'].items():
        if digest((freeze/name).read_bytes())!=sha:raise ValueError('Frozen file changed: '+name)
    import autoresearch_frontier_finance
    runtime_root=Path(autoresearch_frontier_finance.__file__).resolve().parents[2]
    if source_version(runtime_root)['sha256']!=m['runtime']['sha256']:
        raise ValueError('Runtime worktree changed after freeze')
    if digest((ROOT/'data/corpus/processed/manifest.json').read_bytes())!=m['corpus_manifest_sha256']:
        raise ValueError('Corpus manifest changed after freeze')
    corpus=json.loads((ROOT/'data/corpus/processed/manifest.json').read_text())
    for document in corpus['documents']:
        path=ROOT/'data/corpus/processed'/(document['id']+'.md')
        if digest(path.read_bytes())!=document['file_sha256']:
            raise ValueError('Corpus file changed after freeze: '+document['id'])
    return m


async def execute(freeze, *, check=False):
    freeze=Path(freeze).resolve();m=verify_freeze(freeze)
    plan=json.loads((freeze/'run_plan.json').read_text())
    assert len(plan)==24
    budget=json.loads((freeze/'budget_authorization.json').read_text())
    batch=ROOT/'artifacts/experiments'/freeze.name;batch.mkdir(parents=True,exist_ok=True)
    ledger_path=batch/'ledger.json'
    ledger=json.loads(ledger_path.read_text()) if ledger_path.exists() else {'freeze':str(freeze),'entries':[]}
    if check:
        print(json.dumps({'freeze_verified':True,'planned_generations':len(plan),
                          'already_attempted':len(ledger['entries']),'budget':budget}));return
    for index,config in enumerate(plan):
        verify_freeze(freeze)
        key=f"{config['condition_id']}_r{config['repetition']}"
        previous=next((r for r in ledger['entries'] if r['cell']==key),None)
        if previous:
            if previous['status']=='started':
                raise RuntimeError('Unresolved prior process for '+key+'; inspect its process handle before resuming')
            continue  # Failures count; no automatic replacement/revision.
        if sum(r.get('elapsed_seconds',0) for r in ledger['entries'])>=budget['batch_elapsed_budget_seconds']:
            raise RuntimeError('Batch time budget exhausted')
        out=ROOT/'artifacts/runs'/(freeze.name+'_'+key+'_a001')
        entry={'cell':key,'status':'started','run_dir':str(out),
               'started_at':datetime.now(timezone.utc).isoformat()}
        ledger['entries'].append(entry);write_json(ledger_path,ledger)
        started=time.perf_counter()
        config={**config,'experiment_freeze_sha256':digest((freeze/'freeze_manifest.json').read_bytes())}
        if config.get('customization_pair'):
            pair=config['customization_pair']
            basekey=f"{pair['base_condition']}_r{pair['base_repetition']}"
            entry['paired_base_run']=next(r['run_dir'] for r in ledger['entries'] if r['cell']==basekey)
            config['paired_base_run']=entry['paired_base_run']
        try:
            await run(config,out=out)
            result=json.loads((out/'run_manifest.json').read_text())
            entry.update(status=result['status'],automatic_passed=result.get('automatic_passed',False),
                         model_calls=result.get('model_calls'),tokens=(result.get('usage') or {}).get('total_tokens'))
        except Exception as exc:
            entry.update(status='failed',error_type=type(exc).__name__)
        entry['elapsed_seconds']=round(time.perf_counter()-started,3)
        write_json(ledger_path,ledger)
        print(json.dumps({'completed_cells':index+1,'total_cells':24,**entry}),flush=True)
    ledger['complete']=True;write_json(ledger_path,ledger)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--freeze',required=True,type=Path);p.add_argument('--check',action='store_true')
    args=p.parse_args();asyncio.run(execute(args.freeze,check=args.check))
