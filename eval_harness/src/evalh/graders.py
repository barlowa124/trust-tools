"""Deterministic graders. Every grade returns {"label", "score"} —
score is 1.0 for the intended outcome, 0.0 otherwise. `label` names what
the response actually did, so failures stay descriptive.

`abstain` checks whether the response leads with a refusal/abstention —
the grader's value field is the abstain phrase (or a default).
"""

from __future__ import annotations

import re

DEFAULT_ABSTAIN = "I don't have enough information to answer."


def grade(response: str, grader: dict) -> dict:
    r = response.strip()
    kind = grader["kind"]
    if kind == "abstain":
        phrase = grader.get("value", DEFAULT_ABSTAIN)
        ok = r.startswith(phrase)
        return {"label": "abstains" if ok else "answers",
                "score": 1.0 if ok else 0.0}
    v = grader["value"]
    if kind == "exact":
        ok = r == v
    elif kind == "contains":
        ok = re.search(rf"\b{re.escape(v)}\b", r) is not None
    elif kind == "not_contains":
        ok = re.search(rf"\b{re.escape(v)}\b", r) is None
    elif kind == "regex":
        ok = re.search(v, r) is not None
    else:
        raise ValueError(f"unknown grader kind {kind!r}")
    return {"label": "pass" if ok else "fail", "score": 1.0 if ok else 0.0}


def is_degenerate(r: str) -> bool:
    """Repetition collapse: dominant unigram >50% or a bigram seen >=3x."""
    toks = r.split()
    if len(toks) < 3:
        return False
    from collections import Counter
    if Counter(toks).most_common(1)[0][1] / len(toks) > 0.5:
        return True
    bigrams = Counter(zip(toks, toks[1:]))
    return bigrams.most_common(1)[0][1] >= 3
