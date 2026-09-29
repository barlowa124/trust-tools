import json
import os

from conftest import make_devin_db

from trajaudit import devin


def _msg(role, content, tool_calls=None, thinking=None):
    m = {"message_id": "m", "role": role, "content": content}
    if tool_calls:
        m["tool_calls"] = tool_calls
    if thinking:
        m["thinking"] = thinking
    return m


def test_ingest_reconstructs_event_order(tmp_path):
    tc = {"id": "call_1", "name": "exec",
          "arguments": {"command": "pytest -q"}}
    upd = {"status": "completed",
           "content": [{"content": {"type": "text", "text": "3 passed"}}]}
    db = make_devin_db(tmp_path / "sessions.db", [
        _msg("system", "You are Devin"),
        _msg("user", "run the tests"),
        _msg("assistant", "running now", tool_calls=[tc]),
        _msg("assistant", "All 3 tests pass."),
    ], tool_updates={"call_1": upd})

    evs = devin.ingest_session(db, "s1")
    kinds = [e.kind for e in evs]
    assert kinds == ["user", "assistant", "tool_call", "tool_result",
                     "assistant"]
    assert evs[2].args["command"] == "pytest -q"
    assert evs[3].text == "3 passed"
    assert evs[3].args["status"] == "completed"


def test_ingest_emits_plan_events(tmp_path):
    tc = {"id": "call_2", "name": "todo_write",
          "arguments": {"todos": [{"content": "do a", "status": "in_progress"},
                                  {"content": "do b", "status": "pending"}]}}
    db = make_devin_db(tmp_path / "sessions.db", [
        _msg("user", "work"),
        _msg("assistant", "", tool_calls=[tc]),
    ])
    evs = devin.ingest_session(db, "s1")
    plans = [e for e in evs if e.kind == "plan"]
    assert len(plans) == 1
    assert plans[0].plan[0] == {"content": "do a", "status": "in_progress"}


def test_ingest_captures_thinking(tmp_path):
    db = make_devin_db(tmp_path / "sessions.db", [
        _msg("user", "hi"),
        _msg("assistant", "ok", thinking={"thinking": "let me think"}),
    ])
    kinds = [e.kind for e in devin.ingest_session(db, "s1")]
    assert "thinking" in kinds


def test_ingest_skips_system(tmp_path):
    db = make_devin_db(tmp_path / "sessions.db", [
        _msg("system", "system prompt"),
        _msg("user", "hello"),
    ])
    kinds = [e.kind for e in devin.ingest_session(db, "s1")]
    assert kinds == ["user"]


def test_list_sessions(tmp_path):
    db = make_devin_db(tmp_path / "sessions.db", [_msg("user", "x")])
    rows = devin.list_sessions(db)
    assert rows == [{"id": "s1", "title": None, "cwd": "/tmp/ws",
                     "created_at": 1}]


def test_missing_result_is_fine(tmp_path):
    tc = {"id": "call_gone", "name": "exec", "arguments": {"command": "ls"}}
    db = make_devin_db(tmp_path / "sessions.db", [
        _msg("user", "x"),
        _msg("assistant", "", tool_calls=[tc]),
    ])
    evs = devin.ingest_session(db, "s1")
    assert [e.kind for e in evs] == ["user", "tool_call"]
