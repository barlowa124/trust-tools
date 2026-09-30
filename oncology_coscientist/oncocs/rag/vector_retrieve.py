"""Vector-space retrieval over the PDQ corpus.

Two modes behind the same {tag: text} interface as retrieve():

- "tfidf": hashed TF-IDF + cosine, pure numpy, fully offline and
  deterministic. The committed recall comparison uses this mode.
- "embed": E5-small-v2 embeddings via vector-db-mcp
  (pip install vector-db-mcp[embed]). Not bundled; the package must be
  importable at call time.
"""
from __future__ import annotations

import hashlib
import math
from collections import Counter
from pathlib import Path

import numpy as np

from oncocs.config import DEFAULT_ROOT
from oncocs.rag.retrieve import _tokenize, load_passages

# Hash bucket count for the TF-IDF vector space. 2**15 keeps collisions
# rare at this corpus's vocabulary size (~10k tokens).
N_BUCKETS = 1 << 15


def _bucket(token: str) -> int:
    return int.from_bytes(hashlib.blake2b(token.encode(), digest_size=4).digest(), "little") % N_BUCKETS


def _tfidf_vectors(passages: dict[str, str]) -> tuple[dict[str, dict[int, float]], dict[int, float]]:
    """L2-normalized hashed TF-IDF: {tag: {bucket: weight}} plus the idf
    table {bucket: idf} needed to embed queries identically."""
    tags = list(passages)
    tf = {t: Counter(_tokenize(passages[t])) for t in tags}
    df: Counter = Counter()
    for t in tags:
        df.update({_bucket(tok) for tok in tf[t]})
    n = len(tags)
    idf = {b: math.log((n + 1) / (c + 1)) + 1.0 for b, c in df.items()}
    vecs = {}
    for t in tags:
        v = {}
        total = sum(tf[t].values())
        for tok, c in tf[t].items():
            b = _bucket(tok)
            v[b] = v.get(b, 0.0) + (c / total) * idf[b]
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        vecs[t] = {b: x / norm for b, x in v.items()}
    return vecs, idf


def _embed_query_tfidf(query: str, idf: dict[int, float]) -> dict[int, float]:
    tf = Counter(_tokenize(query))
    total = sum(tf.values()) or 1
    v = {}
    for tok, c in tf.items():
        b = _bucket(tok)
        v[b] = v.get(b, 0.0) + (c / total) * idf.get(b, math.log(2))
    norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
    return {b: x / norm for b, x in v.items()}


def retrieve_tfidf(query: str, root: Path | str = DEFAULT_ROOT,
                   top_k: int = 5) -> dict[str, str]:
    passages = load_passages(root)
    if not passages:
        return {}
    vecs, idf = _tfidf_vectors(passages)
    q = _embed_query_tfidf(query, idf)
    scores = {t: sum(w * vecs[t].get(b, 0.0) for b, w in q.items())
              for t in vecs}
    best = sorted(scores, key=scores.get, reverse=True)[:top_k]
    return {t: passages[t] for t in best if scores[t] > 0}


def retrieve_embed(query: str, root: Path | str = DEFAULT_ROOT,
                   top_k: int = 5) -> dict[str, str]:
    """E5 passage embeddings + cosine via vdb_mcp. Requires
    vector-db-mcp[embed]; raises RuntimeError otherwise."""
    try:
        from vdb_mcp.embed import embed_passage, embed_text
    except ImportError as e:
        raise RuntimeError(
            "embed mode needs vector-db-mcp[embed]: pip install "
            "'vector-db-mcp[embed]' or use mode='bm25'/'tfidf'") from e
    passages = load_passages(root)
    if not passages:
        return {}
    tags = list(passages)
    doc = np.stack([embed_passage(passages[t]) for t in tags])
    q = embed_text(query)
    scores = doc @ q
    best = np.argsort(-scores)[:top_k]
    return {tags[i]: passages[tags[i]] for i in best if scores[i] > 0}
