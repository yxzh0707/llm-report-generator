"""Phase-one generic TXT/Markdown ingestion and retrieval smoke harness.

This module validates the dissertation-specific document path without invoking
an LLM or a remote embedding service. It keeps the embedding step behind a
small interface so the same chunks and source metadata can later be passed to
the existing embedding implementation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Iterable, Protocol, Sequence


WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_'-]*|\d+(?:\.\d+)?%?")


@dataclass(frozen=True)
class Document:
    document_id: str
    title: str
    path: str
    source_url: str | None
    text: str
    sha256: str
    file_sha256: str = ''


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    document_id: str
    document_title: str
    source_url: str | None
    text: str
    char_start: int
    char_end: int
    core_char_start: int
    core_char_end: int
    chunk_no: int
    parent_id: str | None = None
    forced_split: bool = False


def _normalise(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text.replace("\r\n", "\n")).strip()


def _metadata(path: Path, text: str) -> tuple[str, str | None]:
    lines = text.splitlines()
    title = path.stem.replace("_", " ")
    if lines and lines[0].startswith("# "):
        title = lines[0][2:].strip() or title
    source_url = next(
        (line.split(":", 1)[1].strip() for line in lines if line.lower().startswith("source url:")),
        None,
    )
    return title, source_url


def load_documents(root: str | Path, ids: Iterable[str] | None = None) -> list[Document]:
    root = Path(root)
    wanted = set(ids or ())
    documents: list[Document] = []
    paths = sorted((*root.glob("*.md"), *root.glob("*.txt")))
    stems = [p.stem for p in paths]
    if len(stems) != len(set(stems)):
        raise ValueError('document_id collision: TXT/Markdown stems must be unique')
    if any(p.is_symlink() for p in paths):
        raise ValueError('uploaded documents must not be symlinks')
    if wanted - set(stems):
        raise ValueError('requested documents are missing')
    for path in paths:
        document_id = path.stem
        if wanted and document_id not in wanted:
            continue
        file_bytes = path.read_bytes()
        raw = _normalise(file_bytes.decode('utf-8'))
        title, source_url = _metadata(path, raw)
        documents.append(Document(
            document_id=document_id,
            title=title,
            path=str(path),
            source_url=source_url,
            text=raw,
            sha256=hashlib.sha256(raw.encode("utf-8")).hexdigest(),
            file_sha256=hashlib.sha256(file_bytes).hexdigest(),
        ))
    if not documents:
        raise ValueError(f"no Markdown or text documents found under {root}")
    return documents


def _units(text: str) -> list[tuple[int, int]]:
    """Return paragraph/heading ranges while preserving source offsets."""
    ranges: list[tuple[int, int]] = []
    cursor = 0
    for block in re.split(r"\n\s*\n", text):
        start = text.find(block, cursor)
        if start < 0:
            continue
        end = start + len(block)
        if block.strip():
            ranges.append((start, end))
        cursor = end
    return ranges


def build_chunks(document: Document, *, target_chars: int = 1000,
                 overlap_chars: int = 0, hard_max_chars: int = 1500) -> list[Chunk]:
    from document_chunking import build_index
    if overlap_chars:
        raise ValueError("Use parent context expansion rather than character overlap")
    return build_index(document, child_target=target_chars, child_max=hard_max_chars)[0]


def _terms(text: str) -> set[str]:
    return {token.lower() for token in WORD_RE.findall(text) if len(token) > 1}


def lexical_retrieve(query: str, chunks: Sequence[Chunk], *, top_k: int = 5) -> list[tuple[float, Chunk]]:
    """Deterministic smoke fallback used before a remote embedding is configured."""
    query_terms = _terms(query)
    if not query_terms:
        return []
    ranked: list[tuple[float, Chunk]] = []
    for chunk in chunks:
        chunk_terms = _terms(chunk.text)
        overlap = query_terms & chunk_terms
        score = len(overlap) / len(query_terms)
        if score:
            ranked.append((score, chunk))
    ranked.sort(key=lambda item: (-item[0], item[1].chunk_id))
    return ranked[:top_k]


class EmbeddingProvider(Protocol):
    """Small adapter contract for a configured embedding service."""

    def embed(self, texts: Sequence[str]) -> Sequence[Sequence[float]]: ...


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or not left:
        raise ValueError("embedding vectors must have the same non-zero dimension")
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = sum(a * a for a in left) ** 0.5
    right_norm = sum(b * b for b in right) ** 0.5
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)


def embedding_retrieve(
    query: str,
    chunks: Sequence[Chunk],
    provider: EmbeddingProvider | Callable[[Sequence[str]], Sequence[Sequence[float]]],
    *,
    top_k: int = 5,
) -> list[tuple[float, Chunk]]:
    """Retrieve with an injected provider; network/model policy stays outside this module."""
    if not chunks:
        return []
    embed = provider.embed if hasattr(provider, "embed") else provider
    vectors = list(embed([query, *(chunk.text for chunk in chunks)]))
    if len(vectors) != len(chunks) + 1:
        raise ValueError("embedding provider returned an unexpected vector count")
    query_vector = vectors[0]
    ranked = [(_cosine(query_vector, vector), chunk) for vector, chunk in zip(vectors[1:], chunks)]
    ranked.sort(key=lambda item: (-item[0], item[1].chunk_id))
    return ranked[:top_k]


def format_context(results: Sequence[tuple[float, Chunk]]) -> str:
    blocks = []
    for index, (score, chunk) in enumerate(results, start=1):
        source = f"[S{index}] {chunk.document_title}"
        if chunk.source_url:
            source += f" — {chunk.source_url}"
        blocks.append(f"{source}\n{chunk.text}\n(relevance={score:.3f}; chunk={chunk.chunk_id})")
    return "\n\n".join(blocks)


def smoke(root: str | Path, query: str) -> dict:
    documents = load_documents(root)
    chunks = [chunk for document in documents for chunk in build_chunks(document)]
    results = lexical_retrieve(query, chunks)
    return {
        "documents": [asdict(document) | {"text": None} for document in documents],
        "document_count": len(documents),
        "chunk_count": len(chunks),
        "query": query,
        "results": [
            {"score": score, "chunk": asdict(chunk)} for score, chunk in results
        ],
        "context": format_context(results),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="data/corpus/processed")
    parser.add_argument("--query", default="NVIDIA data center revenue and AI strategy")
    parser.add_argument("--output", default="artifacts/phase1/phase1_smoke.json")
    args = parser.parse_args()
    result = smoke(args.root, args.query)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("document_count", "chunk_count", "query")}, ensure_ascii=False))
    print(result["context"][:1200])


if __name__ == "__main__":
    main()
