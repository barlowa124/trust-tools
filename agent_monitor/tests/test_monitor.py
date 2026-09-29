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
