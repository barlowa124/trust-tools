import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from trajaudit.model import Event  # noqa: E402


def ev(kind, **kw):
    return Event(i=kw.pop("i", 0), kind=kind, **kw)


def user(text="do the thing"):
    return ev("user", text=text)


def assistant(text="done"):
    return ev("assistant", text=text)


def plan(items):
    return ev("plan", plan=[{"content": c, "status": s} for c, s in items])


def call(tool="exec", command="", **kw):
    args = dict(kw)
    if command:
        args["command"] = command
    return ev("tool_call", tool=tool, args=args)


def result(text="ok", status="completed"):
    return ev("tool_result", text=text, args={"status": status})


def renumber(events):
    for i, e in enumerate(events):
        e.i = i
    return events


def make_devin_db(path, messages, tool_updates=None):
    """Build a minimal sessions.db with the real schema."""
    con = sqlite3.connect(path)
    con.executescript("""
    CREATE TABLE sessions(id TEXT PRIMARY KEY, working_directory TEXT NOT NULL,
      backend_type TEXT NOT NULL, model TEXT NOT NULL, agent_mode TEXT NOT NULL,
      created_at INTEGER NOT NULL, last_activity_at INTEGER NOT NULL,
      title TEXT, main_chain_id INTEGER, shell_last_seen_index INTEGER DEFAULT 0,
      cogs_json TEXT, workspace_dirs TEXT, hidden INTEGER NOT NULL DEFAULT 0,
      metadata TEXT);
    CREATE TABLE message_nodes(row_id INTEGER PRIMARY KEY AUTOINCREMENT,
      session_id TEXT NOT NULL, node_id INTEGER NOT NULL,
      parent_node_id INTEGER, chat_message TEXT NOT NULL,
      created_at INTEGER NOT NULL, metadata TEXT);
    CREATE TABLE tool_call_state(session_id TEXT NOT NULL,
      tool_call_id TEXT NOT NULL, tool_call_json TEXT,
      tool_call_update_json TEXT,
      PRIMARY KEY (session_id, tool_call_id));
    """)
    con.execute(
        "INSERT INTO sessions(id,working_directory,backend_type,model,"
        "agent_mode,created_at,last_activity_at) VALUES('s1','/tmp/ws','x','m','a',1,2)")
    for nid, msg in enumerate(messages):
        con.execute(
            "INSERT INTO message_nodes(session_id,node_id,chat_message,created_at)"
            " VALUES('s1',?,?,?)", (nid, json.dumps(msg), 100 + nid))
    for tcid, upd in (tool_updates or {}).items():
        con.execute(
            "INSERT INTO tool_call_state(session_id,tool_call_id,tool_call_json,"
            "tool_call_update_json) VALUES('s1',?,NULL,?)",
            (tcid, json.dumps(upd)))
    con.commit()
    con.close()
    return str(path)
