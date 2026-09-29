"""attest: hash-chained finding records from an audit report."""
import copy
import json
import unittest

from trajaudit import attest
from trajaudit.cli import main


def _report(n=3):
    return {
        "session": "s-test",
        "n_events": 100,
        "n_findings": n,
        "findings": [
            {"detector": "verification_claim_gap", "event_i": 10 + i,
             "severity": "high", "summary": f"finding {i}",
             "evidence": [f"ev {i}"]}
            for i in range(n)
        ],
    }


class AttestTests(unittest.TestCase):
    def test_chain_links_in_order(self):
        recs = attest.attest_report(_report())
        self.assertEqual(len(recs), 3)
        self.assertEqual(recs[0]["chain_prev"], "genesis")
        for prev, cur in zip(recs, recs[1:]):
            self.assertEqual(cur["chain_prev"], prev["finding_id"])
        self.assertEqual(attest.check_log(recs), [])

    def test_tampered_finding_breaks_hash(self):
        recs = attest.attest_report(_report())
        recs[1]["finding"]["summary"] = "rewritten"
        problems = attest.check_log(recs)
        self.assertTrue(any("tampered" in p for p in problems))

    def test_reorder_breaks_chain(self):
        recs = attest.attest_report(_report())
        recs[0], recs[2] = recs[2], recs[0]
        self.assertTrue(attest.check_log(recs))

    def test_dropped_record_breaks_chain(self):
        recs = attest.attest_report(_report())
        del recs[1]
        self.assertTrue(any("chain break" in p
                            for p in attest.check_log(recs)))

    def test_mixed_logs_flagged(self):
        a = attest.attest_report(_report(1))
        b = attest.attest_report(_report(2))
        mixed = [a[0], b[1]]
        self.assertTrue(any("mixed" in p or "chain" in p
                            for p in attest.check_log(mixed)))

    def test_cli_roundtrip(self):
        import tempfile, os
        with tempfile.TemporaryDirectory() as d:
            rp = os.path.join(d, "r.json")
            op = os.path.join(d, "f.jsonl")
            with open(rp, "w") as f:
                json.dump(_report(), f)
            self.assertEqual(main(["attest", rp, "--out", op]), 0)
            self.assertEqual(main(["verify-attest", op]), 0)
            lines = [json.loads(l) for l in open(op)]
            lines[0]["finding"]["event_i"] = 999
            with open(op, "w") as f:
                for l in lines:
                    f.write(json.dumps(l) + "\n")
            self.assertEqual(main(["verify-attest", op]), 1)


if __name__ == "__main__":
    unittest.main()
