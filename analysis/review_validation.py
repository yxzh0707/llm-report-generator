"""Bind human input to the saved report and evidence; never assign judgments."""
import hashlib
import json
import importlib.metadata
from pathlib import Path
import re
import shutil
import sys
import tempfile
import tarfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from prepare_audit import prepare

EVIDENCE_FIELDS = ('citation', 'source_kind', 'document_id', 'source_url', 'chunk_id',
                   'char_start', 'char_end', 'text_sha256', 'excerpt_sha256', 'text')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def original_proposal(run_dir):
    """Recreate the frozen selection rule in isolation, preserving reviewer files."""
    run_dir = Path(run_dir)
    manifest = json.loads((run_dir / 'run_manifest.json').read_text())
    identity = manifest['code']
    archive = ROOT / 'artifacts/versions/project' / (identity['sha256'] + '.tar.gz')
    if digest(archive.read_bytes()) != identity['archive_sha256']:
        raise ValueError('Original proposal source archive hash mismatch')
    with tarfile.open(archive) as source:
        expected = source.extractfile('src/prepare_audit.py').read()
    if digest(Path(prepare.__code__.co_filename).read_bytes()) != digest(expected):
        raise ValueError('Proposal selector changed since generation; use the archived selector')
    if importlib.metadata.version('pysbd') != manifest['packages']['pysbd']:
        raise ValueError('Proposal sentence-splitter version differs from the recorded run')
    with tempfile.TemporaryDirectory() as temporary:
        copied = Path(temporary) / run_dir.name
        copied.mkdir()
        for name in ('run_manifest.json', 'raw_report.md', 'evidence_ledger.json'):
            shutil.copyfile(run_dir / name, copied / name)
        return json.loads((prepare(copied) / 'review.json').read_text())


def evidence_map(run_dir):
    run_dir = Path(run_dir)
    ledger = json.loads((run_dir / 'evidence_ledger.json').read_text())
    result = {}
    packet_path = run_dir / 'frozen_evidence.json'
    packet = json.loads(packet_path.read_text()) if packet_path.exists() else None
    identity_fields = ('source_kind', 'document_id', 'text_sha256', 'char_start', 'char_end', 'text')
    for source in ledger:
        identity = source['citation']
        if identity in result:
            raise ValueError('Duplicate source identity: ' + identity)
        text = source['text']
        if len(text) != source['char_end'] - source['char_start']:
            raise ValueError('Evidence offset mismatch: ' + identity)
        if digest(text.encode()) != source['excerpt_sha256']:
            raise ValueError('Evidence text hash mismatch: ' + identity)
        if packet is not None and not any(
                all(source.get(k) == candidate.get(k) for k in identity_fields)
                for candidate in packet[source['source_kind']]):
            raise ValueError('Source differs from frozen evidence: ' + identity)
        result[identity] = {k: source.get(k) for k in EVIDENCE_FIELDS}
    return result


def validate_review(run_dir, review):
    """Return validated input/coverage, keeping partial work distinct from completion."""
    run_dir = Path(run_dir)
    original = (run_dir / 'raw_report.md').read_text()
    manifest = json.loads((run_dir / 'run_manifest.json').read_text())
    if (review.get('run_id') != manifest['run_id'] or review.get('run_id') != run_dir.name
            or review.get('raw_report_sha256') != digest(original.encode())
            or manifest['raw_report_sha256'] != digest(original.encode())):
        raise ValueError('Review report identity/hash mismatch')
    if type(review.get('completed')) is not bool:
        raise ValueError('Review completed must be a JSON boolean')
    proposal = original_proposal(run_dir)
    expected = {i['id']: i for i in proposal['items']}
    supplied = review.get('items')
    if not isinstance(supplied, list) or len(supplied) != len(expected) or {
            i.get('id') for i in supplied} != set(expected):
        raise ValueError('Review must retain every proposed item ID without duplicates')
    sources = evidence_map(run_dir)
    body = re.split(r'^#{1,6} Sources\s*$', original, maxsplit=1, flags=re.M)[0]
    items, selected_claims = [], set()
    for item in supplied:
        initial = expected[item['id']]
        if any(item.get(key) != initial[key] for key in ('exact_claim', 'citation_ids', 'evidence')):
            raise ValueError('Original proposal is immutable; record a replacement in selection_change')
        change = item.get('selection_change')
        claim = initial['exact_claim']
        if change is not None:
            if (not isinstance(change, dict) or change.get('original_exact_claim') != initial['exact_claim']
                    or not isinstance(change.get('replacement_exact_claim'), str)
                    or not isinstance(change.get('reason'), str) or not change['reason'].strip()):
                raise ValueError('selection_change requires original_exact_claim, replacement_exact_claim and reason')
            claim = change['replacement_exact_claim']
        if not claim or claim not in body:
            raise ValueError('Review claim must occur verbatim in the saved report body')
        if claim in selected_claims:
            raise ValueError('Repeated factual claim in review')
        selected_claims.add(claim)
        ids = list(dict.fromkeys(re.findall(r'\[S\d+\]', claim)))
        if initial['evidence'] != [sources[i] for i in initial['citation_ids'] if i in sources]:
            raise ValueError('Review evidence text/ranges differ from saved sources: ' + item['id'])
        reviewed_ids = item.get('reviewed_evidence_ids', [i for i in ids if i in sources])
        if (not isinstance(reviewed_ids, list) or not all(isinstance(i, str) and i in sources for i in reviewed_ids)
                or len(reviewed_ids) != len(set(reviewed_ids))):
            raise ValueError('reviewed_evidence_ids must contain unique returned source IDs')
        judgment = item.get('judgment')
        reviewer = item.get('actual_reviewer') or review.get('actual_reviewer')
        if judgment is not None:
            if (judgment not in {'supported', 'contradicted', 'insufficient'}
                    or not isinstance(reviewer, str) or not reviewer.strip()
                    or not isinstance(item.get('reason'), str) or not item['reason'].strip()
                    or item.get('selection_confirmed_by_actual_reviewer') is not True):
                raise ValueError('Graded items require a label, actual reviewer, reason and boolean selection confirmation')
            if judgment in {'supported', 'contradicted'} and not reviewed_ids:
                raise ValueError('Supported/contradicted judgment requires returned evidence IDs')
        items.append({'id': item['id'], 'original_exact_claim': initial['exact_claim'],
                      'exact_claim': claim, 'selection_change': change,
                      'original_citation_ids': initial['citation_ids'],
                      'citation_ids': ids, 'reviewed_evidence_ids': reviewed_ids,
                      'evidence': [sources[i] for i in reviewed_ids], 'judgment': judgment,
                      'reason': item.get('reason'), 'actual_reviewer': reviewer,
                      'review_method':item.get('review_method','human_review' if judgment is not None else None),
                      'confirmation_origin':item.get('confirmation_origin'),
                      'confirmation_record_sha256':item.get('confirmation_record_sha256'),
                      'model_pre_review_reference':item.get('model_pre_review_reference'),
                      'model_selection_suitability':item.get('model_selection_suitability')})
    graded = [i for i in items if i['judgment'] is not None]
    if review['completed'] and (len(graded) != len(expected) or not expected):
        raise ValueError('Review marked complete but not all prespecified items are graded')
    return {'expected_claims': len(expected), 'completed': review['completed'] and bool(expected),
            'items': items, 'reviewed_claims': len(graded),
            'actual_reviewers': sorted({i['actual_reviewer'].strip() for i in graded})}
