"""Export schema and traceable appendix examples from saved formal artifacts."""
import argparse
from dataclasses import MISSING, fields
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
from typing import get_args, get_type_hints, Literal
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from phase1_request_policy import ReportRequest


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')


def request_schema():
    properties, required = {}, []
    hints = get_type_hints(ReportRequest)
    for field in fields(ReportRequest):
        annotation = hints[field.name]
        spec = {'type':'string'}
        if getattr(annotation, '__origin__', None) is Literal:
            spec['enum'] = list(get_args(annotation))
        if field.name == 'task':
            spec.update(minLength=1, pattern=r'\S')
        if field.default is MISSING:
            required.append(field.name)
        else:
            spec['default'] = field.default
        properties[field.name] = spec
    return {'$schema':'https://json-schema.org/draft/2020-12/schema',
            'title':'ReportRequest: implemented CLI request object', 'type':'object',
            'properties':properties, 'required':required, 'additionalProperties':False}


def export(root, freeze):
    root, freeze = Path(root).resolve(), Path(freeze).resolve()
    manifest = json.loads((freeze/'freeze_manifest.json').read_text())
    if manifest['status'] != 'frozen':
        raise ValueError('A finalized freeze is required')
    for name, expected in manifest['files'].items():
        if sha((freeze/name).read_bytes()) != expected:
            raise ValueError('Frozen input changed: '+name)
    ledger = json.loads((root/'artifacts/experiments'/freeze.name/'ledger.json').read_text())
    rows = json.loads((root/'artifacts/tables'/freeze.name/'per_run.json').read_text())
    out = root/'artifacts/appendix'/freeze.name
    out.mkdir(parents=True, exist_ok=True)
    schema = request_schema(); Draft202012Validator.check_schema(schema)
    write(out/'request.schema.json', schema)
    plan = json.loads((freeze/'run_plan.json').read_text())
    for config in plan:
        Draft202012Validator(schema).validate(config['request'])
    observation_schema = {'$schema':schema['$schema'], 'title':'Saved-run appendix observation (presentation only)',
        'type':'object', 'additionalProperties':False,
        'required':['run_id','role','source_run_directory','purpose','request','model','budget','status',
                    'automatic_passed','mechanical_passed','strict_success','usage','model_attempts',
                    'elapsed_seconds','source_kinds','sources','code_sha256','runtime_sha256',
                    'frozen_evidence_sha256','raw_report_sha256','human_content_review_completed'],
        'properties':{'run_id':{'type':'string'}, 'role':{'type':'string'},
            'source_run_directory':{'type':'string'}, 'purpose':{'const':'formal'},
            'request':{k:v for k,v in schema.items() if k!='$schema'}, 'model':{'type':'object'},
            'budget':{'type':'object'},'status':{'type':'string'},'automatic_passed':{'type':'boolean'},
            'mechanical_passed':{'type':'boolean'},'strict_success':{'type':['boolean','null']},
            'usage':{'type':['object','null']},'model_attempts':{'type':'integer','minimum':0},
            'elapsed_seconds':{'type':'number','minimum':0},'source_kinds':{'type':'array','items':{'enum':['uploaded','web']}},
            'sources':{'type':'array'},'code_sha256':{'type':'string','pattern':'^[a-f0-9]{64}$'},
            'runtime_sha256':{'type':'string','pattern':'^[a-f0-9]{64}$'},
            'frozen_evidence_sha256':{'type':'string','pattern':'^[a-f0-9]{64}$'},
            'raw_report_sha256':{'type':'string','pattern':'^[a-f0-9]{64}$'},
            'human_content_review_completed':{'type':'boolean'}}}
    Draft202012Validator.check_schema(observation_schema)
    write(out/'run_observation.schema.json', observation_schema)
    examples = [('automatic_success','T2_uploaded_only_r1'),
                ('constraint_failure','T4_uploaded_only_r1'), ('hybrid_trace','T6_hybrid_r1')]
    records=[]
    for role, cell in examples:
        entry=next(e for e in ledger['entries'] if e['cell']==cell)
        run=root/'artifacts/runs'/Path(entry['run_dir']).name
        m=json.loads((run/'run_manifest.json').read_text())
        a=json.loads((run/'audit.json').read_text())
        row=next(r for r in rows if r['run_id']==m['run_id'])
        if m['code']['sha256']!=manifest['code_sha256']:
            raise ValueError('Example code differs from freeze')
        if sha((run/'raw_report.md').read_bytes())!=m['raw_report_sha256']:
            raise ValueError('Example raw report hash changed')
        if role=='automatic_success' and not a['automatic_passed']:
            raise ValueError('Chosen success is not an automatic pass')
        if role=='constraint_failure' and (a['automatic_passed'] or m['status']!='succeeded'):
            raise ValueError('Chosen failure must illustrate completed generation with a constraint failure')
        target=out/'examples'/role;target.mkdir(parents=True, exist_ok=True)
        copied={}
        for name in ('raw_report.md','report.md','audit.json'):
            shutil.copyfile(run/name,target/name)
            copied[name]=sha((target/name).read_bytes())
        sources=json.loads((run/'evidence_ledger.json').read_text())
        observation={'run_id':m['run_id'],'role':role,'source_run_directory':str(Path('artifacts/runs')/run.name),
            'purpose':m['purpose'],'request':m['request'],'model':manifest['model'],'budget':m['budget'],
            'status':m['status'],'automatic_passed':a['automatic_passed'],
            'mechanical_passed':a['automatic']['mechanical_checks_passed'],'strict_success':row['strict_success'],
            'usage':m['usage'],'model_attempts':m['model_calls'],'elapsed_seconds':m['elapsed_seconds'],
            'source_kinds':sorted({s['source_kind'] for s in sources}),
            'sources':[{k:s.get(k) for k in ('citation','document_id','source_kind','char_start','char_end',
                         'text_sha256','excerpt_sha256','source_url')} for s in sources],
            'code_sha256':m['code']['sha256'],'runtime_sha256':m['runtime']['sha256'],
            'frozen_evidence_sha256':m['frozen_evidence_sha256'],'raw_report_sha256':m['raw_report_sha256'],
            'human_content_review_completed':row['actual_human_review_completed']}
        Draft202012Validator(observation_schema).validate(observation)
        write(target/'observation.json',observation)
        events=[]
        for event in map(json.loads,(run/'trajectory.jsonl').read_text().splitlines()):
            kind=event['type'];data=event['data'];payload=None
            if kind=='model_completed':
                payload={k:data.get(k) for k in ('model_call','physical_attempt','usage','usage_status')}
                payload['provider_response']={k:v for k,v in data.get('provider_response',{}).items()
                                              if k in {'model_name','finish_reason'}}
            elif kind in {'tool_requested','tool_completed','tool_failed'}:
                payload={'tool_call':{k:data['tool_call'].get(k) for k in ('id','name','status')}}
            elif kind in {'run_completed','run_failed'}:
                payload={'terminal':{k:data.get('terminal',{}).get(k) for k in
                                     ('status','error_code','phase','elapsed_s')}}
            if payload is not None:
                events.append({k:event[k] for k in ('seq','type','timestamp')}|{'data':payload})
        write(target/'trajectory_excerpt.json',{
            'scope':'presentation projection; original trajectory remains authoritative',
            'source_sha256':sha((run/'trajectory.jsonl').read_bytes()),
            'omitted':'message deltas, model-input text, tool arguments/results, host and source-package implementation paths',
            'events':events})
        original=os.path.relpath(run,target)
        (target/'README.md').write_text(f'# {role}\n\nSource run: [{run.name}]({original}/run_manifest.json).\n\n'
            'The report and audit files are byte-identical copies. Observation and trajectory excerpt are neutral presentation projections, not replacement raw logs. Runtime completion and automatic constraints are separate; human judgments remain in the review workflow.\n')
        records.append({'role':role,'cell':cell,'run_id':run.name,'copied_source_sha256':copied})
    (out/'README.md').write_text('# Appendix evidence pack\n\n'
        'Generated from the finalized study; it does not run models or alter reports. The JSON schemas describe the implemented request and a saved-run presentation record, not a new HTTP API.\n\n'
        '- [Implemented request schema](request.schema.json)\n'
        '- [Observation schema](run_observation.schema.json)\n'
        '- [Automatic success](examples/automatic_success/README.md)\n'
        '- [Completed report failing a word constraint](examples/constraint_failure/README.md)\n'
        '- [Hybrid trace; inspect its separate automatic outcome](examples/hybrid_trace/README.md)\n\n'
        'Examples are deterministic illustrations, not a success-only evaluation sample. Full machine-specific manifests and trajectories remain linked in the original runs. These projections omit host names and internal source paths. No source-support or tone grade is invented.\n')
    write(out/'manifest.json',{'freeze_id':freeze.name,'freeze_sha256':sha((freeze/'freeze_manifest.json').read_bytes()),
        'exporter_sha256':sha(Path(__file__).read_bytes()),'validated_requests':len(plan),
        'examples':records,'files_sha256':{str(p.relative_to(out)):sha(p.read_bytes()) for p in sorted(out.rglob('*'))
            if p.is_file() and p!=out/'manifest.json'}})
    print(json.dumps({'appendix':str(out),'schemas_validated':2,'request_instances_validated':len(plan),
                      'examples':len(records),'provider_calls':0}))
    return out


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT)
    p.add_argument('--freeze',required=True,type=Path);args=p.parse_args();export(args.root,args.freeze)
