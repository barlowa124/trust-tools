"""BM25 retrieval over the PDQ corpus. No embeddings, no network."""
from __future__ import annotations

import re
from pathlib import Path

from oncocs.config import DEFAULT_ROOT


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def load_passages(root: Path | str = DEFAULT_ROOT) -> dict[str, str]:
    """Return {tag: paragraph_text} where tag is 'PDQ:<doc_id>#<para_idx>'."""
    corpus = Path(root) / "rag" / "corpus"
    passages = {}
    for txt in sorted(corpus.glob("*.txt")):
        doc_id = txt.stem
        for i, para in enumerate(txt.read_text(encoding="utf-8").split("\n\n")):
            para = para.strip()
            if para:
                passages[f"PDQ:{doc_id}#{i}"] = para
    return passages


def retrieve(query: str, root: Path | str = DEFAULT_ROOT, top_k: int = 5,
             mode: str = "bm25") -> dict[str, str]:
    """Top-k passages for the query; returns {tag: text} preserving rank order.

    mode selects the scorer: "bm25" (default), "tfidf" (hashed TF-IDF
    cosine), or "embed" (E5 via vector-db-mcp[embed]).
    """
    if mode == "bm25":
        return _retrieve_bm25(query, root, top_k)
    from oncocs.rag.vector_retrieve import retrieve_embed, retrieve_tfidf
    if mode == "tfidf":
        return retrieve_tfidf(query, root, top_k)
    if mode == "embed":
        return retrieve_embed(query, root, top_k)
    raise ValueError(f"unknown retrieve mode {mode!r}")


def _retrieve_bm25(query: str, root: Path | str = DEFAULT_ROOT,
                   top_k: int = 5) -> dict[str, str]:
    passages = load_passages(root)
    if not passages:
        return {}
    from rank_bm25 import BM25Okapi
    tags = list(passages)
    bm25 = BM25Okapi([_tokenize(passages[t]) for t in tags])
    scores = bm25.get_scores(_tokenize(query))
    best = sorted(range(len(tags)), key=lambda i: scores[i], reverse=True)[:top_k]
    return {tags[i]: passages[tags[i]] for i in best if scores[i] > 0}


def corpus_size_bytes(root: Path | str = DEFAULT_ROOT) -> int:
    corpus = Path(root) / "rag" / "corpus"
    if not corpus.exists():
        return 0
    return sum(p.stat().st_size for p in corpus.iterdir())
