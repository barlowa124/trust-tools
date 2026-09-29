from conftest import (assistant, call, plan, renumber, result, user)

from trajaudit import detectors


def test_plan_drift_flags_novel_addition():
    evs = renumber([
        user(), plan([("write parser", "in_progress"), ("test parser", "pending")]),
        call(command="edit parser.py"),
        plan([("write parser", "completed"), ("test parser", "pending"),
              ("redeploy the service", "pending")]),
    ])
    found = detectors.plan_drift(evs)
    assert len(found) == 1
    assert "redeploy" in found[0]["evidence"][0]


def test_plan_drift_ignores_refinement():
    evs = renumber([
        user(), plan([("write parser", "in_progress")]),
        plan([("write parser core", "completed"), ("test parser", "pending")]),
    ])
    # 'test parser' was not in snapshot 1 but 'write parser core' is a
    # refinement; 'test parser' is novel enough to flag once.
    found = detectors.plan_drift(evs)
    assert len(found) <= 1


def test_abandoned_items_flags_pending_at_end():
    evs = renumber([
        user(), plan([("a", "completed"), ("b", "pending")]),
    ])
    found = detectors.abandoned_items(evs)
    assert any("still pending" in f["summary"] for f in found)


def test_abandoned_items_flags_dropped():
    evs = renumber([
        user(), plan([("a", "in_progress"), ("b", "pending")]),
        plan([("a", "completed")]),
    ])
    found = detectors.abandoned_items(evs)
    assert any("disappeared" in f["summary"] for f in found)


def test_completion_without_verification_flags_unverified():
    evs = renumber([
        user(),
        plan([("run the test suite", "in_progress")]),
        call(command="git status"), result(),
        plan([("run the test suite", "completed")]),
    ])
    found = detectors.completion_without_verification(evs)
    assert len(found) == 1


def test_completion_with_verification_is_clean():
    evs = renumber([
        user(),
        plan([("run the test suite", "in_progress")]),
        call(command="python -m pytest tests/ -q"), result(text="46 passed"),
        plan([("run the test suite", "completed")]),
    ])
    assert detectors.completion_without_verification(evs) == []


def test_claim_gap_flags_unbacked_test_claim():
    evs = renumber([
        user(), call(command="git status"), result(),
        assistant("All 46 tests pass locally."),
    ])
    found = detectors.verification_claim_gap(evs)
    assert len(found) == 1


def test_claim_with_prior_test_run_is_clean():
    evs = renumber([
        user(),
        call(command="python -m pytest tests/ -q"), result(text="46 passed"),
        assistant("All 46 tests pass."),
    ])
    assert detectors.verification_claim_gap(evs) == []


def test_claim_gap_flags_unbacked_deploy_claim():
    evs = renumber([
        user(), call(command="git push"), result(),
        assistant("The fix is deployed and live on production."),
    ])
    found = detectors.verification_claim_gap(evs)
    assert len(found) == 1


def test_scope_drift_flags_outside_writes(tmp_path):
    base = str(tmp_path / "proj")
    evs = renumber([
        user(),
        call(tool="read", file_path="/etc/hostname"),      # reads are recon
        call(tool="edit", file_path=f"{base}/a.py"),
        call(tool="edit", file_path=f"{base}/b.py"),
        call(tool="write", file_path="/etc/evil.conf"),
    ])
    found = detectors.scope_drift(evs)
    assert len(found) == 1
    assert "/etc" in found[0]["evidence"][0]


def test_scope_drift_clean_within_root(tmp_path):
    base = str(tmp_path / "proj")
    evs = renumber([
        user(),
        call(tool="read", file_path=f"{base}/a.py"),
        call(tool="edit", file_path=f"{base}/sub/b.py"),
    ])
    assert detectors.scope_drift(evs) == []


def test_scope_drift_exec_writeish_only(tmp_path):
    base = str(tmp_path / "proj")
    evs = renumber([
        user(),
        call(command=f"ls /System /dev && cd {base}"),
        call(command="cat /etc/passwd > /tmp/leak.txt && mkdir /opt/x"),
        call(command=f"git -C {base} status"),
    ])
    found = detectors.scope_drift(evs)
    flagged = {e for f in found for e in f["evidence"]}
    assert "/opt/x" in flagged or "/tmp" in flagged
    assert "/System" not in flagged and "/dev" not in flagged


def test_unplanned_work_flags_many_calls_no_plan():
    evs = [user()] + [call(command=f"echo {i}") for i in range(25)]
    assert len(detectors.unplanned_work(renumber(evs))) == 1


def test_unplanned_work_clean_with_plan():
    evs = [user(), plan([("x", "in_progress")])] + \
        [call(command=f"echo {i}") for i in range(25)]
    assert detectors.unplanned_work(renumber(evs)) == []


def test_analyze_sorts_findings_by_event():
    evs = renumber([
        user(), plan([("a", "in_progress")]),
        plan([("a", "completed"), ("surprise extra work", "pending")]),
        assistant("All tests pass."),
    ])
    found = detectors.analyze(evs)
    assert found == sorted(found, key=lambda f: (f["event_i"], f["detector"]))
    assert len(found) >= 2


def test_claim_gap_checks_every_claim_type():
    # one message claiming two things: both get evaluated, not just the first
    evs = renumber([
        user(), call(command="pytest -q"), result(),
        assistant("All tests passed and the build is now live on prod."),
    ])
    found = detectors.verification_claim_gap(evs)
    labels = {f["summary"] for f in found}
    assert not any("'test' claim" in s for s in labels)
    assert any("'deploy' claim" in s for s in labels)


def test_claim_gap_both_unbacked_claims_flagged():
    evs = renumber([
        user(),
        assistant("All 12 tests passed and the service is now live on prod."),
    ])
    found = detectors.verification_claim_gap(evs)
    labels = {f["summary"] for f in found}
    assert any("'test' claim" in s for s in labels)
    assert any("'deploy' claim" in s for s in labels)
