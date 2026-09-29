"""Monorepo-level interop: attested audit logs verify with llmreceipt
primitives.

trajaudit vendors the canonical-JSON chain envelope so it stays
dependency-free. This test runs at the monorepo root with both packages on
sys.path and proves the formats agree: every finding_id re-derives under
llmreceipt's canonical_json/sha256, and chain_prev links verify.
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agent_trajectory_audit" / "src"))
sys.path.insert(0, str(ROOT / "inference_receipts" / "src"))
sys.path.insert(0, str(ROOT / "eval_harness" / "src"))
sys.path.insert(0, str(ROOT / "model_serve" / "src"))
sys.path.insert(0, str(ROOT / "receipt_report" / "src"))
sys.path.insert(0, str(ROOT / "agent_monitor" / "src"))


class InteropTests(unittest.TestCase):
    def test_canonical_json_parity_across_packages(self):
        """Every package vendors the same canonical-JSON/SHA-256 envelope.
        If any copy drifts, cross-package chain verification breaks — so
        drift fails here, loudly."""
        from llmreceipt.receipt import (canonical_json as ref_cj,
                                        sha256_bytes as ref_sh)
        from evalh.chainfmt import (canonical_json as ev_cj,
                                    sha256_bytes as ev_sh)
        from modelserve.service import (canonical_json as ms_cj,
                                        sha256_bytes as ms_sh)
        from rcptreport.report import (canonical_json as rr_cj,
                                       sha256_bytes as rr_sh)
        from agentmon.monitor import (canonical_json as am_cj,
                                      sha256_bytes as am_sh)
        probe = {"z": [1, "two", {"nested": None}], "a": True}
        ref = ref_cj(probe)
        for name, cj, sh in (("evalh", ev_cj, ev_sh),
                             ("modelserve", ms_cj, ms_sh),
                             ("rcptreport", rr_cj, rr_sh),
                             ("agentmon", am_cj, am_sh)):
            self.assertEqual(cj(probe), ref, f"{name} canonical_json drift")
            self.assertEqual(sh(b"probe"), ref_sh(b"probe"),
                             f"{name} sha256 drift")

    def test_attest_log_verifies_with_llmreceipt_primitives(self):
        from llmreceipt.receipt import canonical_json, sha256_bytes
        from trajaudit import attest

        report = {
            "session": "interop",
            "n_events": 5,
            "findings": [
                {"detector": "scope_drift", "event_i": i,
                 "severity": "low", "summary": f"f{i}", "evidence": []}
                for i in range(4)
            ],
        }
        records = attest.attest_report(report)

        prev = "genesis"
        for r in records:
            body = {k: v for k, v in r.items() if k != "finding_id"}
            self.assertEqual(
                "fnd-" + sha256_bytes(canonical_json(body))[:16],
                r["finding_id"])
            self.assertEqual(r["chain_prev"], prev)
            prev = r["finding_id"]

    def test_tamper_detected_via_llmreceipt_primitives(self):
        from llmreceipt.receipt import canonical_json, sha256_bytes
        from trajaudit import attest

        records = attest.attest_report(
            {"session": "s", "findings": [{"detector": "d", "event_i": 1,
             "summary": "x"}]})
        records[0]["finding"]["summary"] = "forged"
        body = {k: v for k, v in records[0].items() if k != "finding_id"}
        self.assertNotEqual(
            "fnd-" + sha256_bytes(canonical_json(body))[:16],
            records[0]["finding_id"])


if __name__ == "__main__":
    unittest.main()
