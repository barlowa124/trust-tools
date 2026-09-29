"""Ingest Devin CLI session transcripts (sessions.db, sqlite) into events.

Layout (observed in ~/.local/share/devin/cli/sessions.db):
  sessions(id, working_directory, created_at, title, ...)
  message_nodes(session_id, node_id, chat_message JSON, created_at)
    chat_message: {role, content, tool_calls: [{id,name,arguments}], thinking}
  tool_call_state(session_id, tool_call_id, tool_call_json, tool_call_update_json)
    tool_call_json:  {title, kind, content:[{resource:{text}}]}
    update_json:     {status, content:[{content:{text}}]}

Ordering: assistant messages carry tool_calls inline, so a call's position is
its parent message's node_id plus its index in that message. Results from
tool_call_state are emitted directly after the call they resolve.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from .model import Event

_SUMMARIZE_ARG_KEYS = ("command", "file_path", "path", "pattern", "url",
                       "query", "notebook_path", "resource_uri", "name")


def _arg_summary(tool: str, args: dict) -> dict:
    """Keep the decision-relevant args, not payloads."""
    out = {}
    for k in _SUMMARIZE_ARG_KEYS:
        if k in args and isinstance(args[k], str):
            out[k] = args[k][:500]
    if tool == "exec" and "command" in args:
        out["command"] = str(args["command"])[:500]
    return out


def _result_text(update_json: str | None) -> tuple[str, str]:
    """Return (status, text) from a tool_call_update_json blob."""
    if not update_json:
        return "", ""
    try:
        u = json.loads(update_json)
    except (ValueError, TypeError):
        return "", ""
    status = u.get("status", "")
    texts = []
    for c in u.get("content") or []:
        inner = (c or {}).get("content") or {}
        if isinstance(inner, dict) and isinstance(inner.get("text"), str):
            texts.append(inner["text"])
        elif isinstance(inner, str):
            texts.append(inner)
    return status, "\n".join(texts)


def list_sessions(db_path: str) -> list[dict]:
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    rows = con.execute(
        "SELECT id, title, working_directory, created_at FROM sessions "
        "ORDER BY created_at"
    ).fetchall()
    con.close()
    return [{"id": r[0], "title": r[1], "cwd": r[2], "created_at": r[3]}
            for r in rows]


def ingest_session(db_path: str, session_id: str) -> list[Event]:
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    nodes = con.execute(
        "SELECT node_id, chat_message, created_at FROM message_nodes "
        "WHERE session_id=? ORDER BY node_id", (session_id,)).fetchall()
    results = {
        tcid: upd for tcid, upd in con.execute(
            "SELECT tool_call_id, tool_call_update_json FROM tool_call_state "
            "WHERE session_id=?", (session_id,)).fetchall()
    }
    con.close()

    events: list[Event] = []
    for _node_id, blob, created_at in nodes:
        try:
            msg = json.loads(blob)
        except (ValueError, TypeError):
            continue
        role = msg.get("role")
        content = msg.get("content")
        text = content if isinstance(content, str) else json.dumps(content)[:2000]

        if role == "user":
            events.append(Event(i=len(events), kind="user", session=session_id,
                                t=created_at, text=text))
        elif role == "assistant":
            if isinstance(content, str) and content.strip():
                events.append(Event(i=len(events), kind="assistant",
                                    session=session_id, t=created_at,
                                    text=text))
            thinking = msg.get("thinking")
            if isinstance(thinking, dict) and thinking.get("thinking"):
                events.append(Event(i=len(events), kind="thinking",
                                    session=session_id, t=created_at,
                                    text=thinking["thinking"]))
            for tc in msg.get("tool_calls") or []:
                name = tc.get("name", "")
                args = tc.get("arguments") or {}
                call_id = tc.get("id", "")
                if name == "todo_write":
                    events.append(Event(
                        i=len(events), kind="plan", session=session_id,
                        t=created_at, call_id=call_id,
                        plan=[{"content": t.get("content", ""),
                               "status": t.get("status", "")}
                              for t in args.get("todos", [])]))
                else:
                    events.append(Event(
                        i=len(events), kind="tool_call", session=session_id,
                        t=created_at, tool=name, call_id=call_id,
                        args=_arg_summary(name, args)))
                    if call_id in results:
                        status, rtext = _result_text(results[call_id])
                        events.append(Event(
                            i=len(events), kind="tool_result",
                            session=session_id, t=created_at,
                            call_id=call_id, tool=name,
                            text=rtext[:4000],
                            args={"status": status}))
    return events
