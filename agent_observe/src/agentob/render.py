"""Render an enriched trace: markdown and self-contained HTML.

The report is a span tree with duration, verdict, and the audit
findings section. No JS, no external assets — the HTML file is a
single artifact a reviewer can open directly.
"""

from __future__ import annotations

import html

from . import spans as _spans

_BAR_W = 24


def _bar(frac: float, width: int = _BAR_W) -> str:
    n = max(0, min(width, round(frac * width)))
    return "#" * n + "-" * (width - n)


def _tree_lines(spans: list[dict]) -> list[tuple[dict, int]]:
    out = []

    def walk(sid, depth):
        for s in _spans.children(spans, sid):
            out.append((s, depth))
            walk(s["span_id"], depth + 1)
    walk(None, 0)
    return out


def render_md(report: dict) -> str:
    spans = report["spans"]
    total = max((s["end_ms"] for s in spans), default=0) - \
        min((s["start_ms"] for s in spans), default=0)
    total = total or 1
    lines = [f"# Trace report: {report.get('trace', '')}",
             "",
             f"{len(spans)} spans, {total:.0f} ms wall clock."]
    if report.get("verdicts") is not None:
        acts = {}
        for v in report["verdicts"]:
            acts[v["action"]] = acts.get(v["action"], 0) + 1
        lines.append("Gate verdicts: " + ", ".join(
            f"{k} {n}" for k, n in sorted(acts.items())))
    else:
        lines.append("Gate: not run (agentmon not importable).")
    lines += ["", "## Span tree", "", "```"]
    for s, depth in _tree_lines(spans):
        v = s.get("verdict")
        verdict = (f"  [{v['action']}: {v['rule']}]" if v and v["rule"]
                   else f"  [{v['action']}]" if v else "")
        frac = _spans.duration_ms(s) / total
        lines.append(
            f"{'  ' * depth}{s['name']:<38.38} "
            f"{_spans.duration_ms(s):8.1f}ms {_bar(frac)}{verdict}")
    lines.append("```")
    findings = report.get("findings")
    lines += ["", "## Audit findings", ""]
    if findings is None:
        lines.append("Audit skipped (trajaudit not importable).")
    elif not findings:
        lines.append("No findings.")
    else:
        for f in findings:
            ev = "; ".join(str(e) for e in f.get("evidence", []))
            lines.append(f"- **{f.get('detector', '?')}** "
                         f"{f.get('summary', '')}"
                         + (f" ({ev})" if ev else ""))
    return "\n".join(lines) + "\n"


def render_html(report: dict) -> str:
    spans = report["spans"]
    total = max((s["end_ms"] for s in spans), default=0) - \
        min((s["start_ms"] for s in spans), default=0)
    total = total or 1
    rows = []
    for s, depth in _tree_lines(spans):
        v = s.get("verdict")
        cls = {"deny": "deny", "flag": "flag"}.get(
            (v or {}).get("action"), "ok")
        badge = (f'<span class="{cls}">{html.escape(v["action"])}'
                 + (f': {html.escape(str(v["rule"]))}'
                    if v["rule"] else "")
                 + "</span>" if v else "")
        frac = _spans.duration_ms(s) / total
        rows.append(
            f'<tr class="{cls}">'
            f'<td style="padding-left:{depth * 18 + 8}px">'
            f'{html.escape(str(s["name"]))}</td>'
            f'<td>{html.escape(s["kind"])}</td>'
            f'<td class="num">{_spans.duration_ms(s):.1f} ms</td>'
            f'<td><div class="bar" style="width:{frac * 100:.1f}%"></div></td>'
            f'<td>{badge}</td></tr>')
    findings = report.get("findings")
    if findings is None:
        f_html = "<p>Audit skipped (trajaudit not importable).</p>"
    elif not findings:
        f_html = "<p>No findings.</p>"
    else:
        f_html = "<ul>" + "".join(
            f"<li><b>{html.escape(str(f.get('detector', '?')))}</b> "
            f"{html.escape(str(f.get('summary', '')))} "
            f"<i>{html.escape('; '.join(str(e) for e in f.get('evidence', [])))}</i></li>"
            for f in findings) + "</ul>"
    return f"""<!doctype html><meta charset="utf-8">
<title>Trace report: {html.escape(str(report.get('trace', '')))}</title>
<style>
body{{font-family:system-ui,sans-serif;margin:2rem;max-width:60rem}}
table{{border-collapse:collapse;width:100%}}
td,th{{padding:3px 8px;text-align:left;font-size:.9rem}}
tr.deny td{{background:#fdecea}} tr.flag td{{background:#fff8e1}}
.bar{{height:.7em;background:#90caf9;min-width:1px}}
.num{{font-variant-numeric:tabular-nums;text-align:right}}
.deny,.deny td{{color:#b71c1c}} .flag,.flag td{{color:#e65100}}
</style>
<h1>Trace report: {html.escape(str(report.get('trace', '')))}</h1>
<p>{len(spans)} spans, {total:.0f} ms.</p>
<table><tr><th>span</th><th>kind</th><th>dur</th>
<th></th><th>verdict</th></tr>{''.join(rows)}</table>
<h2>Audit findings</h2>{f_html}
"""
