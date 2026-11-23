"""Sentence-aware parent/child indexing with exact normalized-text offsets."""
import re
from dataclasses import replace
import pysbd
from phase1_document_retrieval import Chunk

VERSION = 'sentence-parent-child-v1'


def _spans(text, start, end, target, hard_max):
    segmenter = pysbd.Segmenter(language='en', clean=False, char_span=True)
    # Paragraph boundaries remain preferred. Sentence detection handles abbreviations
    # and decimal numbers, unlike splitting on every period.
    boundaries = []
    for paragraph in re.finditer(r'\S[\s\S]*?(?=\n[ \t]*\n|\Z)', text[start:end]):
        base = start + paragraph.start()
        for sentence in segmenter.segment(paragraph.group()):
            boundaries.append(base + sentence.end)
    if not boundaries or boundaries[-1] < end:
        boundaries.append(end)
    atoms, cursor = [], start
    for boundary in boundaries:
        while boundary - cursor > hard_max:
            limit = cursor + hard_max
            candidates = [m.end() for m in re.finditer(r'\s+', text[cursor:limit])]
            cut = cursor + candidates[-1] if candidates else limit
            atoms.append((cursor, cut, True))
            cursor = cut
        if boundary > cursor:
            atoms.append((cursor, boundary, False))
            cursor = boundary
    groups = []
    for a, b, forced in atoms:
        if groups and b - groups[-1][0] <= target and not groups[-1][2] and not forced:
            groups[-1] = (groups[-1][0], b, False)
        else:
            groups.append((a, b, forced))
    return groups


def build_index(document, child_target=1000, child_max=1500, parent_target=2400, parent_max=4000):
    if not 0 < child_target <= child_max <= parent_max or not 0 < parent_target <= parent_max:
        raise ValueError('Invalid parent/child budgets')
    parents, children = {}, []
    for n, (a, b, forced) in enumerate(_spans(document.text, 0, len(document.text), parent_target, parent_max)):
        pid = f'{document.document_id}:{VERSION}:p{n:04d}'
        parent = Chunk(pid, document.document_id, document.title, document.source_url,
                       document.text[a:b], a, b, a, b, n, None, forced)
        parents[pid] = parent
        for c, d, child_forced in _spans(document.text, a, b, child_target, child_max):
            number = len(children)
            children.append(replace(parent, chunk_id=f'{pid}:c{number:04d}', parent_id=pid,
                text=document.text[c:d], char_start=c, char_end=d,
                core_char_start=c, core_char_end=d, chunk_no=number,
                forced_split=forced or child_forced))
    return children, parents


def expand_parents(results, parents, max_chars=18000):
    expanded, seen, total = [], set(), 0
    for score, child in results:
        parent = parents[child.parent_id]
        if parent.chunk_id in seen or total + len(parent.text) > max_chars:
            continue
        expanded.append((score, parent))
        seen.add(parent.chunk_id)
        total += len(parent.text)
    return expanded
