import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "agent_observe", "src"))
sys.path.insert(0, os.path.join(ROOT, "agent_monitor", "src"))
sys.path.insert(0, os.path.join(ROOT, "agent_trajectory_audit", "src"))

import agentob  # noqa: E402
from agentob import spans  # noqa: E402

EXAMPLE = os.path.join(ROOT, "agent_observe", "examples",
                       "agent_run.json")


def _span(**kw):
    d = {"span_id": "a", "parent_id": None, "name": "a",
         "kind": "step", "start_ms": 0, "end_ms": 10, "attrs": {}}
    d.update(kw)
    return d


class IngestTests(unittest.TestCase):
    def test_load_example(self):
        trace = spans.load(EXAMPLE)
        self.assertEqual(len(trace), 9)
        tools = spans.tool_spans(trace)
        self.assertEqual(len(tools), 5)

    def test_duplicate_ids_rejected(self):
        with tempfile.NamedTemporaryFile(
                "w", suffix=".json", delete=False) as f:
            json.dump([_span(), _span()], f)
        try:
            with self.assertRaises(spans.TraceError):
                spans.load(f.name)
        finally:
            os.unlink(f.name)

    def test_unknown_parent_rejected(self):
        with tempfile.NamedTemporaryFile(
                "w", suffix=".json", delete=False) as f:
            json.dump([_span(parent_id="ghost")], f)
        try:
            with self.assertRaises(spans.TraceError):
                spans.load(f.name)
        finally:
            os.unlink(f.name)

    def test_end_before_start_rejected(self):
        with tempfile.NamedTemporaryFile(
                "w", suffix=".json", delete=False) as f:
            json.dump([_span(end_ms=-5)], f)
        try:
            with self.assertRaises(spans.TraceError):
                spans.load(f.name)
        finally:
            os.unlink(f.name)

    def test_otlp_lite(self):
        export = {"resourceSpans": [{"scopeSpans": [{"spans": [
            {"spanId": "x1", "name": "run",
             "startTimeUnixNano": "0",
             "endTimeUnixNano": "1000000",
             "attributes": [
                 {"key": "gen_ai.tool.name", "value": {"stringValue": "exec"}},
                 {"key": "args",
                  "value": {"stringValue": "{\"cmd\":\"ls\"}"}}]}]}]}]}
        with tempfile.NamedTemporaryFile(
                "w", suffix=".json", delete=False) as f:
            json.dump(export, f)
        try:
            trace = spans.load(f.name)
        finally:
            os.unlink(f.name)
        self.assertEqual(len(trace), 1)
        self.assertEqual(trace[0]["kind"], "tool_call")
        self.assertEqual(trace[0]["attrs"]["tool"], "exec")
        self.assertEqual(trace[0]["end_ms"], 1.0)


class EnrichTests(unittest.TestCase):
    def setUp(self):
        from agentmon.policy import load_policy
        from agentmon.redteam import default_policy_path
        self.policy = load_policy(default_policy_path())
        self.trace = spans.load(EXAMPLE)

    def test_verdicts_attach(self):
        verdicts = agentob.gate_spans(self.trace, self.policy,
                                    cwd=os.path.dirname(EXAMPLE))
        by_tool = {s["name"]: s.get("verdict")
                   for s in self.trace if s["kind"] == "tool_call"}
        self.assertEqual(by_tool["write_file config"]["action"], "allow")
        self.assertEqual(by_tool["exec curl|sh"]["action"], "deny")
        self.assertEqual(by_tool["exec sudo rm"]["action"], "deny")
        self.assertEqual(by_tool["read .env"]["action"], "deny")
        self.assertEqual(by_tool["exec wget"]["action"], "flag")
        self.assertEqual(len(verdicts), 5)

    def test_to_events_schema(self):
        events = agentob.to_events(self.trace)
        from trajaudit.model import Event
        parsed = [Event.from_dict(e) for e in events]
        kinds = [e.kind for e in parsed]
        self.assertEqual(kinds.count("tool_call"), 5)
        self.assertIn("tool_result", kinds)
        self.assertIn("assistant", kinds)

    def test_audit_runs(self):
        events = agentob.to_events(self.trace)
        findings = agentob.audit(events)
        self.assertIsNotNone(findings)
        # final span claims deploy + tests pass with no verification
        detectors = {f["detector"] for f in findings}
        self.assertIn("verification_claim_gap", detectors)

    def test_monitor_records_alerts(self):
        from agentmon.monitor import Monitor
        m = Monitor(self.policy, cwd=os.path.dirname(EXAMPLE),
                    log_allows=False)
        agentob.gate_spans(self.trace, self.policy,
                           cwd=os.path.dirname(EXAMPLE), monitor=m)
        actions = {r["verdict"]["action"]
                   for r in m.records}
        self.assertEqual(len(m.records), 4)   # 3 deny + 1 flag
        self.assertEqual(actions, {"deny", "flag"})


class RenderTests(unittest.TestCase):
    def _report(self):
        from agentmon.policy import load_policy
        from agentmon.redteam import default_policy_path
        trace = spans.load(EXAMPLE)
        verdicts = agentob.gate_spans(
            trace, load_policy(default_policy_path()),
            cwd=os.path.dirname(EXAMPLE))
        return {"trace": "agent_run.json", "spans": trace,
                "verdicts": verdicts,
                "findings": agentob.audit(agentob.to_events(trace))}

    def test_render_md(self):
        md = agentob.render_md(self._report())
        self.assertIn("Span tree", md)
        self.assertIn("verification_claim_gap", md)
        self.assertIn("deny", md)

    def test_render_html(self):
        h = agentob.render_html(self._report())
        self.assertIn("<table>", h)
        self.assertIn("verification_claim_gap", h)
        self.assertIn("deny", h)


class CliTests(unittest.TestCase):
    def test_report_end_to_end(self):
        from agentob.cli import main
        with tempfile.TemporaryDirectory() as d:
            ev_p = os.path.join(d, "events.jsonl")
            al_p = os.path.join(d, "alerts.jsonl")
            md_p = os.path.join(d, "report.md")
            rc = main(["report", EXAMPLE,
                       "--cwd", os.path.dirname(EXAMPLE),
                       "--events", ev_p, "--alerts", al_p,
                       "--html", os.path.join(d, "report.html")])
            self.assertEqual(rc, 0)
            from trajaudit.model import read_jsonl
            evs = read_jsonl(ev_p)
            self.assertTrue(len(evs) > 0)
            alerts = [json.loads(l)
                      for l in open(al_p) if l.strip()]
            self.assertEqual(len(alerts), 4)
            self.assertTrue(
                os.path.exists(os.path.join(d, "report.html")))


if __name__ == "__main__":
    unittest.main()
