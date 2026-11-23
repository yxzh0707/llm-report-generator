"""Minimal report-generation input pipeline for the dissertation prototype.

This module assembles a validated request and retrieved chunks into a
source-numbered Markdown prompt package. An LLM adapter can consume the
package; the assembly and citation identifiers remain deterministic.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

from phase1_document_retrieval import Chunk, format_context, lexical_retrieve, load_documents
from phase1_request_policy import ReportRequest, allowed_tools, required_headings


@dataclass(frozen=True)
class SourceRef:
    citation: str
    chunk_id: str
    document_id: str
    title: str
    source_url: str | None
    char_start: int
    char_end: int
    forced_split: bool = False


def assemble_context(results: Sequence[tuple[float, Chunk]]) -> tuple[str, list[SourceRef]]:
    refs: list[SourceRef] = []
    for index, (_, chunk) in enumerate(results, start=1):
        refs.append(SourceRef(
            citation=f"[S{index}]", chunk_id=chunk.chunk_id,
            document_id=chunk.document_id, title=chunk.document_title,
            source_url=chunk.source_url, char_start=chunk.char_start, char_end=chunk.char_end,
            forced_split=chunk.forced_split,
        ))
    return format_context(results), refs


def build_prompt_package(request: ReportRequest, root: str | Path, *, top_k: int = 8,
                         document_ids: Sequence[str] | None = None, embedding_provider=None,
                         retrieval_queries: Sequence[str] | None = None) -> dict:
    request.validate()
    if request.source_mode != "uploaded_only":
        raise NotImplementedError("phase-one local pipeline currently implements uploaded_only")
    started = time.perf_counter()
    documents = load_documents(root, ids=document_ids)
    if document_ids is not None and set(document_ids) != {d.document_id for d in documents}:
        raise ValueError("requested documents are missing")
    from document_chunking import build_index, expand_parents, VERSION
    chunks, parents = [], {}
    for document in documents:
        child_chunks, parent_chunks = build_index(document)
        chunks.extend(child_chunks)
        parents.update(parent_chunks)
    chunks = [c for c in chunks if any(
        line.strip() and not line.lstrip().startswith(('#', 'Source URL:', '---'))
        for line in c.text.splitlines())]
    if top_k < 1:
        raise ValueError('top_k must be positive')
    queries = list(retrieval_queries or [request.task])
    rankings = []
    for query in queries:
        if embedding_provider is None:
            rankings.append(lexical_retrieve(query, chunks, top_k=top_k))
        else:
            from phase1_document_retrieval import embedding_retrieve
            rankings.append(embedding_retrieve(query, chunks, embedding_provider, top_k=top_k))
    # Round-robin across task facets, with a fixed total context budget.
    results, seen = [], set()
    for rank in range(top_k):
        for ranking in rankings:
            if rank < len(ranking) and len(results) < top_k:
                result = ranking[rank]
                if result[1].chunk_id not in seen:
                    results.append(result)
                    seen.add(result[1].chunk_id)
    child_hits = [{"chunk_id": c.chunk_id, "parent_id": c.parent_id,
                   "score": score, "char_start": c.char_start, "char_end": c.char_end,
                   "forced_split": c.forced_split} for score, c in results]
    results = expand_parents(results, parents)
    context, refs = assemble_context(results)
    headings = required_headings(request.structure)
    instructions = (
        "Write an English Markdown report. Follow the requested structure, style, and depth. "
        "Cite every material factual claim with the provided [S#] identifiers. "
        "Do not invent sources or cite information outside the supplied context. "
        "Distinguish reported facts, calculated metrics and supported interpretations. "
        "Omit unsupported causal or competitive claims. Missing excerpts do not imply "
        "that the original document lacks the information."
    )
    return {
        "request": asdict(request),
        "documents": [{"document_id": d.document_id, "sha256": d.sha256} for d in documents],
        "allowed_tools": sorted(allowed_tools(request.source_mode)),
        "required_headings": list(headings),
        "instructions": instructions,
        "context": context,
        "sources": [asdict(ref) for ref in refs],
        "retrieval": {"method": "embedding_cosine" if embedding_provider else "lexical_smoke",
                      "chunking_version": VERSION, "child_hits": child_hits,
                      "context_max_chars": 18000, "context_chars": sum(len(c.text) for _, c in results),
                      "queries": queries, "merge": "round_robin_unique_chunks",
                      "top_k": top_k, "result_count": len(results),
                      "represented_documents": sorted({c.document_id for _, c in results})},
        "run": {"status": "prepared", "elapsed_ms": round((time.perf_counter() - started) * 1000, 2)},
    }


def _document_chunks(document):
    # Imported lazily so this module keeps the public entry point small.
    from phase1_document_retrieval import build_chunks
    return build_chunks(document)


def render_report_sources(report: str, sources: Sequence[dict]) -> str:
    """Keep raw model output separately; render traceable sources from metadata."""
    body = re.split(r'^#{1,2}[ \t]+Sources[ \t]*$', report, maxsplit=1, flags=re.M)[0].rstrip()
    cited = set(re.findall(r'\[S\d+\]', body))
    lines = []
    for source in sources:
        if source['citation'] in cited:
            if source.get('source_kind') == 'web':
                lines.append(f"- {source['citation']} {source['title']} — {source['source_url']}, "
                             f"snapshot `{source['text_sha256']}`, characters "
                             f"[{source['char_start']}, {source['char_end']}). "
                             f"Retrieved {source['retrieved_at']}; publication date unverified.")
                continue
            lines.append(f"- {source['citation']} {source['title']} — "
                         f"document ID `{source['document_id']}`, chunk `{source['chunk_id']}`, "
                         f"characters [{source['char_start']}, {source['char_end']}) "
                         f"in normalized uploaded text. Original: {source['source_url'] or 'local upload'}")
    return body + '\n\n## Sources\n\n' + '\n'.join(lines) + '\n'


if __name__ == "__main__":
    request = ReportRequest(task="Summarise NVIDIA's data centre business and AI strategy")
    package = build_prompt_package(request, "data/corpus/processed", document_ids=[
        "nvidia_fy2025_10k", "nvidia_fy2025_q4_cfo_commentary"])
    Path("artifacts/phase1").mkdir(parents=True, exist_ok=True)
    Path("artifacts/phase1/phase1_nvidia_prompt_package.json").write_text(
        json.dumps(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"status": package["run"]["status"], "sources": len(package["sources"]), "elapsed_ms": package["run"]["elapsed_ms"]}))
