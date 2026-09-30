"""Deterministic claim verifier: every number in the draft must trace to results."""
from __future__ import annotations

import re
from typing import Any

REQUIRED_SECTIONS = ["## Cohort", "## Models and metrics",
                     "## Checks and abstentions", "## Limitations"]

FORBIDDEN_PHRASES = [
    "clinically validated",
    "proves",
    "causes",
    "should be used",
    "outperforms",
    "state-of-the-art",
]

FORBIDDEN_REGEXES = [
    # a concordance/discrimination index must not be described as calibration
    (re.compile(r"(harrell|uno|c-index|concordance)[^.]{0,60}calibrat", re.I),
     "C-index described as calibration"),
]

# A leading '-' is part of the number only when it isn't preceded by a
# word char/digit/dot — so "0.5-0.6" still extracts 0.5 and 0.6, while
# " -0.544" keeps its sign (sign flips must not verify against +0.544).
_NUM_RE = re.compile(r"(?<![\w.%])-?\d[\d,]*(?:\.\d+)?\s*%?(?![\w.%])")
_SIG_RE = re.compile(r"\bsignificant\b", re.IGNORECASE)
_PNUM_RE = re.compile(r"p\s*[=<≤]\s*(0?\.\d+|1\.0+|<\s*0?\.\d+)", re.IGNORECASE)


def flatten_results(obj: Any, prefix: str = "") -> dict[str, float]:
    """Flatten every numeric leaf of a results-like dict to {dotted.path: value}."""
    out: dict[str, float] = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.update(flatten_results(v, f"{prefix}{k}."))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out.update(flatten_results(v, f"{prefix}{i}."))
    elif isinstance(obj, bool):
        pass
    elif isinstance(obj, (int, float)):
        out[prefix[:-1]] = float(obj)
    return out


def extract_numbers(text: str) -> list[dict]:
    """Numeric tokens with display precision and context."""
    tokens = []
    for m in _NUM_RE.finditer(text):
        raw = m.group(0).strip()
        is_pct = raw.endswith("%")
        val = raw.rstrip("%").replace(",", "")
        decimals = len(val.split(".")[1]) if "." in val else 0
        ctx = text[max(0, m.start() - 30): m.end() + 30].replace("\n", " ")
        tokens.append({"token": raw, "value": float(val), "is_pct": is_pct,
                       "decimals": decimals, "context": ctx.strip(),
                       "pos": m.start()})
    return tokens


def _section_span(draft: str, name: str) -> tuple[int, int] | None:
    m = re.search(r"^##\s*" + re.escape(name) + r"\s*$", draft, re.I | re.M)
    if not m:
        return None
    nxt = re.search(r"^##\s", draft[m.end():], re.M)
    end = m.end() + nxt.start() if nxt else len(draft)
    return m.start(), end


def _checks_section(draft: str) -> str:
    m = re.search(r"##\s*Checks and abstentions\s*\n(.*?)(?=\n\s*##|\Z)",
                  draft, re.S | re.I)
    return m.group(1) if m else ""


_CITE_RE = re.compile(r"\[PDQ:([A-Za-z0-9_.\-]+)#(\d+)\]")
_QUOTE_THEN_TAG = re.compile(r'"([^"]{10,})"\s*(\[PDQ:[^\]]+\])')
_TAG_THEN_QUOTE = re.compile(r'(\[PDQ:[^\]]+\])\s*"([^"]{10,})"')


def _has_section(draft: str, title: str) -> bool:
    return bool(re.search(r"^##\s*" + re.escape(title[3:]) + r"\s*$",
                          draft, re.I | re.M))


def _model_scopes(draft: str, model_keys: list) -> list:
    """Segment the draft by model-key mentions at heading/bullet/paragraph starts.
    Returns list of (start, end, model_key) covering the draft."""
    mentions = []
    for key in sorted(model_keys, key=len, reverse=True):
        for m in re.finditer(r"(?m)^[>\s*#\-]*" + re.escape(key) + r"(?![\w/])",
                             draft):
            mentions.append((m.start(), key))
    mentions.sort()
    scopes = []
    for i, (pos, key) in enumerate(mentions):
        end = mentions[i + 1][0] if i + 1 < len(mentions) else len(draft)
        scopes.append((pos, end, key))
    return scopes


def verify_draft(draft: str, flat_values: dict[str, float],
                 checks: list[dict], models: dict | None = None,
                 focus_models: list | None = None,
                 passages: dict | None = None) -> dict:
    values = list(flat_values.values())
    unverified, forbidden, missing = [], [], []
    misattributed, missing_focus, unscoped_model = [], [], []

    # Integers embedded in metric key names are labels, not model values:
    # integrated_brier_6_36m -> {6, 36}; auc_12m/24m/36m -> {12, 24, 36}.
    label_ints = set()
    for k in flat_values:
        for seg in k.split("."):
            m = re.search(r"_(\d+)(?:_(\d+))?m$", seg)
            if m:
                label_ints.update(int(x) for x in m.groups() if x)

    # per-model value sets and global (non-model) values for scoped checks
    model_vals = {}
    global_vals = []
    if models:
        for key, out in models.items():
            model_vals[key] = list(flatten_results(out).values())
        global_vals = [v for k, v in flat_values.items()
                       if not any(k == f"models.{mk}" or k.startswith(f"models.{mk}.")
                                  for mk in models)]
    scopes = _model_scopes(draft, list(models)) if models else []

    # --- citation / context-section checks (PDQ passages) ---
    passages = passages or {}
    unknown_citations, misquotes = [], []
    ctx_span = _section_span(draft, "Context")
    for m in _CITE_RE.finditer(draft):
        if m.group(0).strip("[]") not in passages:
            unknown_citations.append(m.group(0))
    quote_tag_pairs = [
        (m.group(1), m.group(2)) for m in _QUOTE_THEN_TAG.finditer(draft)
    ]
    quote_tag_pairs += [
        (m.group(2), m.group(1)) for m in _TAG_THEN_QUOTE.finditer(draft)
    ]
    for quote, tag in quote_tag_pairs:
        if tag.strip("[]") in passages and quote not in passages[tag.strip("[]")]:
            misquotes.append({"tag": tag, "quote": quote})
    tag_spans = [(m.start(), m.end()) for m in _CITE_RE.finditer(draft)]
    ctx_text = draft[ctx_span[0]:ctx_span[1]] if ctx_span else ""
    ctx_passage_text = ""
    if ctx_span:
        cited_in_ctx = {m.group(0).strip("[]") for m in _CITE_RE.finditer(ctx_text)}
        ctx_passage_text = " ".join(
            passages[t] for t in cited_in_ctx if t in passages).replace(",", "")

    def _scope_of(pos: int) -> str | None:
        owner = None
        for start, end, key in scopes:
            if start <= pos < end:
                owner = key
        return owner

    for tok in extract_numbers(draft):
        v, tol = tok["value"], 0.5 * 10 ** (-tok["decimals"])
        if any(s <= tok["pos"] < e for s, e in tag_spans):
            continue  # digits inside citation tags are not claims
        if ctx_span and ctx_span[0] <= tok["pos"] < ctx_span[1]:
            # numbers in Context must come from the cited passages, not results
            if tok["token"].rstrip("%").replace(",", "") not in ctx_passage_text:
                unverified.append({"token": tok["token"],
                                   "context": "context section (not in cited passage)"})
            continue

        def _matches(vs, v=v, tol=tol, is_pct=tok["is_pct"]):
            frac = v / 100.0 if is_pct else None
            # a percentage token is also a fraction; its tolerance scales down
            return any(abs(v - fv) <= tol for fv in vs) or (
                frac is not None and
                any(abs(frac - fv) <= tol / 100.0 for fv in vs))

        scope = _scope_of(tok["pos"]) if scopes else None
        if scope:
            ok = _matches(model_vals[scope]) or _matches(global_vals)
            if not ok:
                owners = [k for k, vs in model_vals.items() if k != scope and _matches(vs)]
                if owners:
                    misattributed.append({"token": tok["token"],
                                          "attributed_to": scope,
                                          "actually_in": owners,
                                          "context": tok["context"]})
                    continue
        else:
            ok = _matches(values)
            is_label = tok["decimals"] == 0 and int(v) in label_ints
            if ok and models and not is_label and not _matches(global_vals):
                owners = [k for k, vs in model_vals.items() if _matches(vs)]
                if owners:
                    unscoped_model.append({"token": tok["token"],
                                           "found_in": owners,
                                           "context": tok["context"]})
                    continue
        if not ok and tok["decimals"] == 0 and int(v) in label_ints:
            ok = True
        if not ok:
            unverified.append({"token": tok["token"], "context": tok["context"]})

    if models and focus_models:
        for fm in focus_models:
            if fm in models and fm not in draft:
                missing_focus.append(fm)

    low = draft.lower()
    for phrase in FORBIDDEN_PHRASES:
        # word-bounded: "improves"/"approves" must not trip "proves"
        if re.search(r"\b" + re.escape(phrase) + r"\b", low):
            forbidden.append(phrase)
    if re.search(r"\brobust\b", low):
        forbidden.append("robust")
    for rx, label in FORBIDDEN_REGEXES:
        if rx.search(draft):
            forbidden.append(label)

    for m in _SIG_RE.finditer(draft):
        window = draft[m.end(): m.end() + 40]
        pm = _PNUM_RE.search(window)
        ok = False
        if pm:
            num = pm.group(1).replace("<", "").strip()
            pv = float(num)
            tol = 0.5 * 10 ** (-len(num.split(".")[1])) if "." in num else 0.5
            ok = any(abs(pv - fv) <= tol for fv in values)
        if not ok:
            forbidden.append(f"significant (unverified p-value near offset {m.start()})")

    for sec in REQUIRED_SECTIONS:
        if not _has_section(draft, sec):
            missing.append(sec)

    abstention_missing = False
    if any(c.get("passed") is False for c in checks):
        abstention_missing = "abstain" not in _checks_section(draft).lower()

    return {
        "passed": (not unverified and not forbidden and not missing
                   and not abstention_missing and not misattributed
                   and not missing_focus and not unscoped_model
                   and not unknown_citations and not misquotes),
        "unverified_numbers": unverified,
        "unknown_citations": unknown_citations,
        "misquotes": misquotes,
        "unscoped_model_numbers": unscoped_model,
        "misattributed": misattributed,
        "missing_focus_models": missing_focus,
        "forbidden": forbidden,
        "missing_sections": missing,
        "abstention_missing": abstention_missing,
    }
