"""Verify immutable corpus bytes, normalized offsets and deterministic retrieval."""
import json
from pathlib import Path
from document_chunking import build_index, VERSION
from phase1_document_retrieval import load_documents, lexical_retrieve
from provenance import write_json, digest


def verify(root):
    root = Path(root)
    manifest = json.loads((root / 'manifest.json').read_text())
    docs = load_documents(root)
    assert {d.document_id for d in docs} == {d['id'] for d in manifest['documents']}
    rows = []
    for doc in docs:
        frozen = next(d for d in manifest['documents'] if d['id'] == doc.document_id)
        assert frozen.get('file_sha256', frozen['sha256']) == doc.file_sha256
        if 'normalized_text_sha256' in frozen:
            assert frozen['normalized_text_sha256'] == doc.sha256
        children, parents = build_index(doc)
        for blocks in (children, list(parents.values())):
            assert blocks[0].char_start == 0 and blocks[-1].char_end == len(doc.text)
            assert ''.join(c.text for c in blocks) == doc.text
            assert all(doc.text[c.char_start:c.char_end] == c.text for c in blocks)
        assert all(parents[c.parent_id].char_start <= c.char_start < c.char_end
                   <= parents[c.parent_id].char_end for c in children)
        query = 'data center revenue AI strategy risks'
        assert lexical_retrieve(query, children) == lexical_retrieve(query, list(reversed(children)))
        rows.append({'document_id': doc.document_id, 'file_sha256': doc.file_sha256,
                     'normalized_text_sha256': doc.sha256, 'normalized_chars': len(doc.text),
                     'children': len(children), 'parents': len(parents),
                     'child_forced_splits': sum(c.forced_split for c in children),
                     'parent_forced_splits': sum(c.forced_split for c in parents.values())})
    return {'passed': True, 'manifest_sha256': digest((root / 'manifest.json').read_bytes()),
            'chunking_version': VERSION, 'documents': rows}


if __name__ == '__main__':
    result = verify('data/corpus/processed')
    out = Path('artifacts/verification/corpus.json')
    out.parent.mkdir(parents=True, exist_ok=True)
    write_json(out, result)
    print(json.dumps(result))
