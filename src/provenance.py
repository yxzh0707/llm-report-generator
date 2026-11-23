"""Non-secret fingerprints and JSON artifacts shared by development and runtime runs."""
import hashlib
import json
import platform
import sys
import subprocess
import tarfile
from pathlib import Path


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def source_version(root):
    root = Path(root)
    paths = sorted(p for folder in ('src', 'tests', 'configs', 'experiments')
                   for p in (root / folder).rglob('*')
                   if p.is_file() and '__pycache__' not in p.parts
                   and p.suffix in {'.py', '.json', '.yaml', '.yml', '.md', '.html', '.css', '.js'})
    paths += [root / name for name in ('requirements.txt', 'requirements-runtime.lock.txt', 'pyproject.toml', 'uv.lock')
              if (root / name).is_file()]
    files = {str(p.relative_to(root)): digest(p.read_bytes()) for p in sorted(paths)}
    return {'algorithm': 'sha256-relative-path-map-v1', 'files': files,
            'sha256': digest(json.dumps(files, sort_keys=True).encode())}


def environment():
    return {'python': sys.version, 'platform': platform.platform(), 'hostname': platform.node()}


def snapshot(root, destination):
    """Archive only enumerated code/config files, never env files or credentials."""
    root, destination = Path(root), Path(destination)
    version = source_version(root)
    destination.mkdir(parents=True, exist_ok=True)
    stem = destination / version['sha256']
    archive = stem.with_suffix('.tar.gz')
    if not archive.exists():
        with tarfile.open(archive, 'w:gz') as tar:
            for name in version['files']:
                tar.add(root / name, arcname=name, recursive=False)
        write_json(stem.with_suffix('.json'), version)
        git = subprocess.run(['git', '-C', str(root), 'rev-parse', 'HEAD'], capture_output=True, text=True)
        if git.returncode == 0:
            patch = subprocess.run(['git', '-C', str(root), 'diff', '--', 'src', 'configs',
                                    'pyproject.toml', 'uv.lock'], capture_output=True)
            stem.with_suffix('.patch').write_bytes(patch.stdout)
            version['git_commit'] = git.stdout.strip()
            version['tracked_patch_sha256'] = digest(patch.stdout)
            write_json(stem.with_suffix('.json'), version)
    saved = json.loads(stem.with_suffix('.json').read_text())
    return {'sha256': version['sha256'], 'archive': str(archive),
            'archive_sha256': digest(archive.read_bytes()), 'git_commit': saved.get('git_commit'),
            'tracked_patch_sha256': saved.get('tracked_patch_sha256')}
