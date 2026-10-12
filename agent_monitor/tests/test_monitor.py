"""agentmon: policy evaluation, live gating, chained alert log."""
import json
import os
import tempfile
import unittest

from agentmon.monitor import DenyError, Monitor, check_log
from agentmon.policy import evaluate, load_policy

POLICY = {
    "defaults": {"action": "allow"},
    "rules": [
        {"id": "no-sudo", "tool": "exec", "arg_regex": r"\bsudo\b",
         "action": "deny", "severity": "high", "reason": "privesc"},
        {"id": "writes-in-scope", "tool": "write", "arg_field": "file_path",
         "path_scope": ["./"], "action": "deny_outside",
         "severity": "medium", "reason": "out of scope"},
        {"id": "net", "tool": "exec", "arg_regex": r"\bcurl\b",
         "action": "flag", "severity": "low", "reason": "network"},
    ],
}


class PolicyTests(unittest.TestCase):
    def test_deny_beats_flag(self):
        v = evaluate(POLICY, "exec", {"command": "sudo curl x"})
        self.assertEqual(v.action, "deny")
        self.assertEqual(v.rule, "no-sudo")

    def test_flag_when_no_deny(self):
        v = evaluate(POLICY, "exec", {"command": "curl example.com"})
        self.assertEqual(v.action, "flag")

    def test_default_allow(self):
        v = evaluate(POLICY, "exec", {"command": "ls"})
        self.assertEqual(v.action, "allow")
        self.assertIsNone(v.rule)

    def test_deny_outside_scope(self):
        with tempfile.TemporaryDirectory() as d:
            sub = os.path.join(d, "proj")
            os.makedirs(sub)
            v = evaluate(POLICY, "write", {"file_path": "/etc/x"}, cwd=sub)
            self.assertEqual(v.action, "deny")
            self.assertEqual(v.rule, "writes-in-scope")
            v2 = evaluate(POLICY, "write",
                          {"file_path": os.path.join(sub, "f.py")},
                          cwd=sub)
            self.assertEqual(v2.action, "allow")

    def test_dotdot_escape_denied(self):
        with tempfile.TemporaryDirectory() as d:
            v = evaluate(POLICY, "write",
                         {"file_path": os.path.join(d, "sub/../esc")},
                         cwd=d)
            # d/sub/../esc normalizes to d/esc — still inside d, allow
            self.assertEqual(v.action, "allow")
            v2 = evaluate(POLICY, "write",
                          {"file_path": os.path.join(d, "../out")},
                          cwd=d)
            self.assertEqual(v2.action, "deny")

    def test_unrelated_tool_skipped(self):
        v = evaluate(POLICY, "read", {"file_path": "/etc/passwd"})
        self.assertEqual(v.action, "allow")

    def test_arg_aliases_cannot_bypass_scope(self):
        """cmd/command and path/file_path aliasing was a real bypass:
        agent_sandbox's battery showed {"cmd": ...} sails past rules
        keyed on "command". Aliases must not reopen it."""
        pol = load_policy(os.path.join(
            os.path.dirname(__file__), "..", "policies",
            "default.json"))
        for args in ({"command": "echo p > /tmp/x"},
                     {"cmd": "echo p > /tmp/x"},
                     {"command_line": "echo p > /tmp/x"}):
            v = evaluate(pol, "exec", args, cwd="/tmp/sbx")
            self.assertEqual(v.action, "deny",
                             f"{args} bypassed exec-writes-in-scope")
        for args in ({"file_path": "/etc/x"}, {"path": "/etc/x"}):
            v = evaluate(pol, "write", args, cwd="/tmp/sbx")
            self.assertEqual(v.action, "deny",
                             f"{args} bypassed writes-in-scope")

    def test_nonredirect_writes_cannot_bypass_scope(self):
        """cp/mv/install destinations were the battery's next residual:
        no redirect token means the old regex extracted nothing."""
        pol = load_policy(os.path.join(
            os.path.dirname(__file__), "..", "policies",
            "default.json"))
        for cmd in ("cp a.txt /tmp/x",
                    "mv a.txt /tmp/x",
                    "install -m 644 a.txt /tmp/x",
                    "cp a.txt /tmp/x && cp b.txt ./ok",
                    "dd if=a.txt of=/tmp/x",
                    "rsync -a a.txt /tmp/x"):
            v = evaluate(pol, "exec", {"command": cmd}, cwd="/tmp/sbx")
            self.assertEqual(v.action, "deny",
                             f"{cmd!r} bypassed exec-writes-in-scope")
        # Destinations inside scope must still pass.
        for cmd in ("cp a.txt ./b.txt", "mv a.txt sub/b.txt",
                    "echo hi > ./x.txt"):
            v = evaluate(pol, "exec", {"command": cmd}, cwd="/tmp/sbx")
            self.assertNotEqual(v.action, "deny",
                                f"{cmd!r} wrongly denied")

    def test_policy_validation(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json",
                                         delete=False) as f:
            json.dump({"rules": [{"id": "x"}]}, f)
            p = f.name
        with self.assertRaises(ValueError):
            load_policy(p)


class GateTests(unittest.TestCase):
    def test_deny_raises_before_call(self):
        m = Monitor(POLICY)
        ran = []
        with self.assertRaises(DenyError):
            m.gate("exec", {"command": "sudo rm"})
        self.assertFalse(ran)
        self.assertEqual(len(m.records), 1)

    def test_flag_records_not_raises(self):
        m = Monitor(POLICY)
        v = m.gate("exec", {"command": "curl x"})
        self.assertEqual(v.action, "flag")
        self.assertEqual(len(m.records), 1)

    def test_allow_not_logged_by_default(self):
        m = Monitor(POLICY)
        m.gate("exec", {"command": "ls"})
        self.assertEqual(len(m.records), 0)

    def test_wrap_gates_and_runs(self):
        m = Monitor(POLICY)
        @m.wrap("exec", arg_fn=lambda cmd: {"command": cmd})
        def sh(cmd):
            return f"ran:{cmd}"
        self.assertEqual(sh("ls"), "ran:ls")
        with self.assertRaises(DenyError):
            sh("sudo ls")

    def test_alert_chain_verifies(self):
        m = Monitor(POLICY)
        m.gate("exec", {"command": "curl a"})
        m.gate("exec", {"command": "curl b"})
        try:
            m.gate("exec", {"command": "sudo x"})
        except DenyError:
            pass
        self.assertEqual(len(m.records), 3)
        self.assertEqual(m.records[0]["chain_prev"], "genesis")
        self.assertEqual(check_log(m.records), [])
        m.records[1]["verdict"]["reason"] = "forged"
        self.assertTrue(check_log(m.records))


if __name__ == "__main__":
    unittest.main()


class EventExportTests(unittest.TestCase):
    """agentmon.events: gated calls become trajaudit-schema events."""

    def _recorder(self):
        from agentmon.events import EventRecorder
        from agentmon.monitor import Monitor
        pol = {"defaults": {"action": "allow"},
               "rules": [{"id": "no-sudo", "tool": "exec",
                          "arg_regex": "sudo",
                          "action": "deny", "severity": "high",
                          "reason": "priv"}]}
        return EventRecorder(Monitor(pol), session="s1")

    def test_allowed_call_records_pair(self):
        rec = self._recorder()
        rec.gate("exec", {"command": "ls"})
        self.assertEqual(len(rec.events), 2)
        self.assertEqual(rec.events[0]["kind"], "tool_call")
        self.assertEqual(rec.events[0]["args"]["command"], "ls")
        self.assertIn("monitor: allow", rec.events[1]["text"])
        self.assertEqual(rec.events[0]["call_id"],
                         rec.events[1]["call_id"])

    def test_denied_call_still_recorded(self):
        rec = self._recorder()
        with self.assertRaises(Exception):
            rec.gate("exec", {"command": "sudo rm x"})
        kinds = [e["kind"] for e in rec.events]
        self.assertEqual(kinds, ["tool_call", "tool_result"])
        self.assertIn("deny", rec.events[1]["text"])

    def test_write_jsonl_roundtrip_under_trajaudit(self):
        """The emitted stream parses under trajaudit's own reader."""
        import sys, tempfile, os
        root = os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))))
        sys.path.insert(0, os.path.join(
            root, "agent_trajectory_audit", "src"))
        rec = self._recorder()
        rec.gate("exec", {"command": "ls"})
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl",
                                         delete=False) as f:
            path = f.name
        try:
            rec.write_jsonl(path)
            from trajaudit.model import read_jsonl
            evs = read_jsonl(path)
            self.assertEqual(len(evs), 2)
            self.assertEqual(evs[0].kind, "tool_call")
        finally:
            os.unlink(path)


class RedTeamBatteryTests(unittest.TestCase):
    """agentmon.redteam: adversarial cases against the default policy."""

    def setUp(self):
        from agentmon.redteam import (run_battery, default_policy_path)
        from agentmon.policy import load_policy
        self.results = {r["attack"]: r
                        for r in run_battery(load_policy(
                            default_policy_path()))}

    def test_violations_detected(self):
        residual = {"symlink_write", "encoded_exfil"}
        for name, r in self.results.items():
            if r["expect"] == "violation" and name not in residual:
                self.assertEqual(r["status"], "detected",
                                 f"{name} regressed")

    def test_benigns_clean(self):
        for name, r in self.results.items():
            if r["expect"] == "benign":
                self.assertEqual(r["status"], "clean",
                                 f"{name} over-blocks")

    def test_symlink_is_documented_residual(self):
        """Symlink scope escapes are the known residual: string-level
        checks cannot resolve filesystem links. If this ever becomes
        'detected', the gate gained realpath resolution — update the
        docstring and the README either way."""
        self.assertIn(self.results["symlink_write"]["status"],
                      ("detected", "EVADED"))

    def test_only_documented_evasion(self):
        evaded = {a for a, r in self.results.items()
                  if r["status"] == "EVADED"}
        self.assertEqual(evaded, {"symlink_write", "encoded_exfil"})

    def test_split_secret_detected(self):
        """Whitespace-splitting is the cheap evasion for token regexes;
        the squash pass exists to rejoin it."""
        r = self.results["split_token_leak"]
        self.assertEqual(r["status"], "detected")
        self.assertEqual(r["action"], "deny")


class OutputGateTests(unittest.TestCase):
    """Output-side policy: emitted answers evaluated against
    output_rules — secrets, structure contracts, length."""

    POL = {
        "defaults": {"action": "allow"},
        "rules": [],
        "output_rules": [
            {"id": "no-token", "squash_regex": "sk-[A-Za-z0-9]{20,}",
             "action": "deny", "severity": "high",
             "reason": "token-shaped output"},
            {"id": "must-json", "format": "json",
             "require_keys": ["answer"],
             "fields": {"confidence": {"type": "number",
                                      "min": 0, "max": 1},
                        "answer": {"type": "str", "required": True,
                                   "min_len": 1}},
             "action": "deny", "severity": "medium",
             "reason": "answer contract"},
            {"id": "needs-cite", "text_regex_require": r"\[\d+\]",
             "action": "flag", "severity": "low",
             "reason": "uncited answer"},
            {"id": "too-long", "max_chars": 100, "action": "flag",
             "severity": "low", "reason": "verbose"},
        ],
    }

    def test_clean_json_answer_passes(self):
        from agentmon.outgate import evaluate_output
        v = evaluate_output(self.POL,
                            '{"answer": "4 [1]", "confidence": 0.9}')
        self.assertEqual(v.action, "allow")

    def test_token_leak_denied(self):
        from agentmon.outgate import evaluate_output
        v = evaluate_output(self.POL,
                            'key: sk-' + 'x7' * 24)
        self.assertEqual(v.action, "deny")
        self.assertEqual(v.rule, "no-token")

    def test_split_token_denied(self):
        from agentmon.outgate import evaluate_output
        v = evaluate_output(self.POL,
                            'key: sk- ' + 'x7' * 12 + ' ' + 'x7' * 12)
        self.assertEqual(v.action, "deny")

    def test_deny_beats_flag_on_output(self):
        from agentmon.outgate import evaluate_output
        v = evaluate_output(
            self.POL, '{"answer": "' + 'sk-' + 'x7' * 24 + '"}')
        self.assertEqual(v.action, "deny")
        self.assertEqual(v.rule, "no-token")

    def test_non_json_violates_contract(self):
        from agentmon.outgate import evaluate_output
        v = evaluate_output(self.POL, "four [1]")
        self.assertEqual(v.action, "deny")
        self.assertEqual(v.rule, "must-json")

    def test_missing_required_field_denied(self):
        from agentmon.outgate import evaluate_output
        v = evaluate_output(self.POL, '{"confidence": 0.5}')
        self.assertEqual(v.action, "deny")
        self.assertIn("answer", v.reason)

    def test_field_out_of_range_denied(self):
        from agentmon.outgate import evaluate_output
        v = evaluate_output(self.POL,
                            '{"answer": "ok [1]", "confidence": 2}')
        self.assertEqual(v.action, "deny")

    def test_bool_is_not_int(self):
        from agentmon.outgate import evaluate_output
        pol = {"output_rules": [
            {"id": "r", "format": "json",
             "fields": {"n": {"type": "int"}}, "action": "deny"}]}
        v = evaluate_output(pol, '{"n": true}')
        self.assertEqual(v.action, "deny")

    def test_required_pattern_absent_flags(self):
        from agentmon.outgate import evaluate_output
        pol = {"output_rules": [
            {"id": "needs-cite", "text_regex_require": r"\[\d+\]",
             "action": "flag"}]}
        v = evaluate_output(pol, "no citations here")
        self.assertEqual(v.action, "flag")
        v2 = evaluate_output(pol, "cited [1]")
        self.assertEqual(v2.action, "allow")

    def test_max_chars_flags(self):
        from agentmon.outgate import evaluate_output
        pol = {"output_rules": [
            {"id": "cap", "max_chars": 10, "action": "flag"}]}
        self.assertEqual(evaluate_output(pol, "x" * 11).action, "flag")
        self.assertEqual(evaluate_output(pol, "x" * 10).action, "allow")

    def test_gate_output_raises_and_records(self):
        m = Monitor(self.POL)
        with self.assertRaises(DenyError):
            m.gate_output('sk-' + 'y9' * 24)
        self.assertEqual(len(m.records), 1)
        self.assertEqual(m.records[0]["side"], "output")
        self.assertEqual(m.records[0]["tool"], "<output>")

    def test_wrap_output_gates_return(self):
        m = Monitor(self.POL)

        @m.wrap_output
        def emit():
            return "sk-" + "z1" * 24

        with self.assertRaises(DenyError):
            emit()

    def test_mixed_input_output_chain_verifies(self):
        pol = {"defaults": {"action": "allow"},
               "rules": [{"id": "net", "tool": "exec",
                          "arg_regex": "curl", "action": "flag"}],
               "output_rules": self.POL["output_rules"]}
        m = Monitor(pol)
        m.gate("exec", {"command": "curl a"})
        m.gate_output('{"answer": "' + "x" * 200 +
                      ' [1]", "confidence": 0.5}')
        try:
            m.gate_output("sk-" + "w5" * 24)
        except DenyError:
            pass
        self.assertEqual(len(m.records), 3)
        self.assertEqual(m.records[0]["side"], "input")
        self.assertEqual(m.records[1]["side"], "output")
        self.assertEqual(check_log(m.records), [])

    def test_output_policy_validation(self):
        from agentmon.outgate import validate_output_rules
        with self.assertRaises(ValueError):
            validate_output_rules([{"id": "x"}])
        with self.assertRaises(ValueError):
            validate_output_rules(
                [{"id": "x", "action": "deny",
                  "fields": {"a": {"type": "funky"}}}])
        with self.assertRaises(ValueError):
            validate_output_rules(
                [{"id": "x", "action": "deny", "bogus_key": 1}])
