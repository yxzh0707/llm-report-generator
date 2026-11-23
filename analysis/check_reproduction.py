"""Restore hashed source archives in isolation and verify offline assembly."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import sysconfig
import tarfile
import tempfile

ROOT=Path(__file__).resolve().parents[1]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def restore(root, identity, category, destination):
    archive=root/'artifacts/versions'/category/(identity['sha256']+'.tar.gz')
    if sha(archive.read_bytes())!=identity['archive_sha256']:
        raise ValueError('Archive hash mismatch: '+category)
    with tarfile.open(archive) as source:
        for member in source.getmembers():
            name=PurePosixPath(member.name)
            if name.is_absolute() or '..' in name.parts or not member.isfile():
                raise ValueError('Unexpected source archive member')
        source.extractall(destination,filter='data')
    return str(archive)


CHILD = r'''
import asyncio,importlib.metadata,json,sys,re
from pathlib import Path
import urllib.request,httpx,requests
root,runtime=(Path(p).resolve() for p in sys.argv[1:3]);expected=json.loads(sys.argv[3])
attempts=[]
def denied(*a,**kw):
    attempts.append('HTTP');raise AssertionError('HTTP is forbidden in offline reproduction check')
async def denied_async(*a,**kw):
    return denied()
urllib.request.urlopen=denied;httpx.Client.send=denied;httpx.AsyncClient.send=denied_async
requests.sessions.Session.request=denied
import autoresearch_frontier_finance,run_report
assert Path(autoresearch_frontier_finance.__file__).resolve().is_relative_to(runtime/'src')
assert Path(run_report.__file__).resolve().is_relative_to(root/'src')
from provenance import source_version
assert source_version(root)['sha256']==expected['code']
assert source_version(runtime)['sha256']==expected['runtime']
pins={}
for line in (root/'requirements-runtime.lock.txt').read_text().splitlines():
    if not line.strip() or line.startswith('#'):continue
    match=re.fullmatch(r'([A-Za-z0-9_.-]+)==(.+)',line)
    assert match, 'Unsupported dependency lock entry'
    name,version=match.groups();actual=importlib.metadata.version(name)
    assert actual==version, 'Dependency version mismatch: '+name
    pins[name]=actual
from experiments.run_experiments import preflight
pre=preflight();assert pre['passed']
from offline_smoke import main
out=asyncio.run(main());m=json.loads((out/'run_manifest.json').read_text())
sources=json.loads((out/'evidence_ledger.json').read_text())
assert m['status']=='succeeded' and m['model']=='fake_fixture'
assert m['code']['sha256']==expected['code'] and m['runtime']['sha256']==expected['runtime']
assert {s['document_id'] for s in sources}=={'a','b'}
assert m['embedding_calls']==0 and not attempts
for name in ['request.json','resolved_config.json','raw_report.md','report.md','audit.json','trajectory.jsonl','run_manifest.json']:
    assert (out/name).is_file()
print(json.dumps({'restored_project_hash':m['code']['sha256'],'restored_runtime_hash':m['runtime']['sha256'],
    'corpus_verified':True,'fixture_document_ids':sorted({s['document_id'] for s in sources}),
    'fake_runtime_status':m['status'],'http_attempts':len(attempts),'embedding_calls':0,
    'artifact_contract_passed':True,'quality_result':False,
    'validated_dependency_pins':len(pins),
    'dependency_versions':m['packages']}))
'''


def check(root,freeze):
    root,freeze=Path(root).resolve(),Path(freeze).resolve()
    m=json.loads((freeze/'freeze_manifest.json').read_text())
    if m['status']!='frozen':raise ValueError('Finalize the freeze first')
    corpus=root/'data/corpus/processed'
    if sha((corpus/'manifest.json').read_bytes())!=m['corpus_manifest_sha256']:
        raise ValueError('Corpus manifest hash mismatch')
    original_fixture=json.loads((root/'artifacts/runs/20261020T031222625614Z/corpus_manifest.json').read_text())
    expected_fixtures={r['id']:r['file_sha256'] for r in original_fixture}
    output=root/'artifacts/verification/reproduction';output.mkdir(parents=True,exist_ok=True)
    attempt=output/f'attempt-{len(list(output.glob("attempt-*")))+1:03d}'
    attempt.mkdir()
    asset_root=root/'artifacts/reproducibility/fixtures'
    asset_root.mkdir(parents=True,exist_ok=True)
    fixture_records={}
    for filename in ('a.md','b.txt'):
        source=root/'tests/fixtures/documents'/filename
        if not source.exists():source=asset_root/filename
        data=source.read_bytes()
        if sha(data)!=expected_fixtures[Path(filename).stem]:
            raise ValueError('Fixture differs from saved original offline input: '+filename)
        (asset_root/filename).write_bytes(data)
        fixture_records[filename]=sha(data)
    with tempfile.TemporaryDirectory(prefix='reportgen-reproduction-') as temporary:
        project=Path(temporary)/'project';runtime=Path(temporary)/'runtime'
        project.mkdir();runtime.mkdir()
        project_archive=restore(root,m['code_snapshot'],'project',project)
        runtime_archive=restore(root,m['runtime'],'runtime',runtime)
        missing_assets=[]
        for filename in fixture_records:
            destination=project/'tests/fixtures/documents'/filename
            if not destination.exists():missing_assets.append(str(destination.relative_to(project)))
            destination.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(asset_root/filename,destination)
        # Corpus is frozen input, deliberately separate from the code archive.
        shutil.copytree(corpus,project/'data/corpus/processed')
        env={k:v for k,v in os.environ.items() if k in {'PATH','HOME','LANG','LC_ALL','SSL_CERT_FILE','SSL_CERT_DIR'}}
        env.update(PYTHONPATH=os.pathsep.join((str(runtime/'src'),str(project/'src'),sysconfig.get_path('purelib'))),
                   LANGCHAIN_TRACING_V2='false')
        # Skip .pth editable-install hooks so an existing working-tree install
        # cannot masquerade as the restored runtime. Dependencies stay explicit.
        process=subprocess.run([sys.executable,'-S','-c',CHILD,str(project),str(runtime),
            json.dumps({'code':m['code_sha256'],'runtime':m['runtime']['sha256']})],
            cwd=project,env=env,capture_output=True,text=True,timeout=60)
        (attempt/'stdout.log').write_text(process.stdout)
        (attempt/'stderr.log').write_text(process.stderr)
        (attempt/'status.json').write_text(json.dumps({'exit_code':process.returncode,
            'project_sha256':m['code_sha256'],'runtime_sha256':m['runtime']['sha256']},indent=2)+'\n')
        if process.returncode:raise RuntimeError('Restored offline run failed; see '+str(attempt/'stderr.log'))
        result=json.loads(process.stdout.splitlines()[-1])
    result.update(scope='archived code + saved corpus/fixtures + existing pinned Python environment; no fresh pip install claimed',
        frozen_id=freeze.name,project_archive=project_archive,runtime_archive=runtime_archive,
        restored_supplemental_assets=missing_assets,fixture_sha256=fixture_records,
        checker_sha256=sha(Path(__file__).read_bytes()),
        attempt_directory=str(attempt),editable_install_hooks_disabled=True,
        fixture_artifact_lifetime='temporary test fixture; original study artifacts remain unchanged')
    (output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    (asset_root/'manifest.json').write_text(json.dumps({'scope':'input fixtures omitted by code-only source archive',
        'original_offline_run':'20261020T031222625614Z','files_sha256':fixture_records},indent=2)+'\n')
    print(json.dumps(result,indent=2))
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT)
    p.add_argument('--freeze',required=True,type=Path);args=p.parse_args();check(args.root,args.freeze)
