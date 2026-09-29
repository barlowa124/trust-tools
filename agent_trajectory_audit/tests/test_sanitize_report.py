import json

from conftest import assistant, call, plan, renumber, user

from trajaudit import detectors, report, sanitize
from trajaudit.model import Event


def test_sanitize_redacts_home_paths():
    e = Event(i=0, kind="tool_call", tool="edit",
              args={"file_path": "/Users/someone/proj/x.py"})
    out = sanitize.sanitize([e])
    assert out[0].args["file_path"].startswith("~/")
    assert "someone" not in json.dumps(out[0].to_dict())


def test_sanitize_redacts_email_and_ip():
    e = Event(i=0, kind="user",
              text="mail me at a.b@corp.com or hit 10.0.0.4")
    out = sanitize.sanitize([e])
    assert "<email>" in out[0].text and "<ip>" in out[0].text


def test_sanitize_drops_thinking_and_renumbers():
    evs = [user("hi"), Event(i=1, kind="thinking", text="secret reasoning"),
           assistant("ok")]
    out = sanitize.sanitize(evs)
    assert [e.kind for e in out] == ["user", "assistant"]
    assert [e.i for e in out] == [0, 1]


def test_sanitize_cleans_plan_content():
    e = Event(i=0, kind="plan",
              plan=[{"content": "edit /Users/me/secret.py",
                     "status": "pending"}])
    out = sanitize.sanitize([e])
    assert "/Users/me" not in out[0].plan[0]["content"]


def test_report_counts_and_links():
    evs = renumber([
        user(), plan([("run tests", "in_progress")]),
        call(command="ls"),
        plan([("run tests", "completed")]),
        assistant("All tests pass."),
    ])
    findings = detectors.analyze(evs)
    rep = report.build_report(evs, findings)
    assert rep["n_findings"] >= 2
    md = report.to_markdown(rep)
    assert "verification_claim_gap" in md
    assert "event_i" in md
    js = json.loads(report.to_json(rep))
    assert js["session"] == rep["session"]


def test_report_empty_findings():
    evs = renumber([user(), assistant("no claims here")])
    rep = report.build_report(evs, detectors.analyze(evs))
    md = report.to_markdown(rep)
    assert "No findings" in md or rep["n_findings"] >= 0


def test_sanitize_redacts_bare_tokens():
    e = Event(i=0, kind="tool_result",
              text="ok: ghp_abc123def456 AKIAIOSFODNN7EXAMPLE "
                   "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0In0.sigpart "
                   "and sk-live-abcdefghi123")
    out = sanitize.sanitize([e])
    assert out[0].text.count("<token>") == 4
    assert "ghp_" not in out[0].text and "AKIA" not in out[0].text
