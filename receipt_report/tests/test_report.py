"""Report tests — synthetic chains, verified end to end."""
import json
import os
import tempfile
import unittest

from rcptreport.report import (check_chain, detect_kind, load_log,
                               render)


def _eval_records(n=4):
    """Minimal valid eval_result chain (same construction as evalh)."""
    import hashlib
    def cj(o):
        return json.dumps(o, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False).encode()
    def sh(b):
        return hashlib.sha256(b).hexdigest()
    recs, prev = [], "genesis"
    for i in range(n):
        out = f"out{i}"
        body = {"v": 1, "created_at": "t", "kind": "eval_result",
                "model": {"name": "m1"},
                "spec_sha256": "abc",
                "task_id": f"t{i}", "tag": "answerable" if i % 2
                        else "unanswerable",
                "output": {"text": out, "sha256": sh(out.encode())},
                "grade": {"label": "pass" if i % 2 else "abstains",
                          "score": 1.0 if i % 2 else 0.0,
                          "grader": {"kind": "contains"}},
                "chain_prev": prev}
        body["result_id"] = "evr-" + sh(cj(body))[:16]
        recs.append(body)
        prev = body["result_id"]
    return recs


def _write(recs):
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as f:
        for r in recs:
            f.write(json.dumps(r) + "\n")
    return path


class ReportTests(unittest.TestCase):
    def test_detect_kind(self):
        self.assertEqual(detect_kind(_eval_records()), "eval_result")

    def test_check_clean_chain(self):
        self.assertEqual(check_chain(_eval_records()), [])

    def test_check_tampered(self):
        recs = _eval_records()
        recs[1]["grade"]["score"] = 99.0
        self.assertTrue(check_chain(recs))

    def test_render_eval(self):
        path = _write(_eval_records())
        try:
            md = render([path], title="t")
        finally:
            os.unlink(path)
        self.assertIn("Evaluation run", md)
        self.assertIn("chain verified", md)
        self.assertIn("answerable", md)
        self.assertIn("All chains verified", md)

    def test_render_tampered_shows_finding(self):
        recs = _eval_records()
        recs[2]["output"]["text"] = "forged"
        path = _write(recs)
        try:
            md = render([path])
        finally:
            os.unlink(path)
        self.assertIn("CHAIN INTEGRITY", md)
        self.assertIn("failed chain verification", md)

    def test_report_limits_present(self):
        path = _write(_eval_records(1))
        try:
            md = render([path])
        finally:
            os.unlink(path)
        self.assertIn("## Limits", md)
        self.assertIn("not a capability or safety claim", md)

    def test_mixed_log_flagged(self):
        recs = _eval_records(2)
        recs[1] = dict(recs[1], kind="serve_response",
                       response_id=recs[1].pop("result_id"))
        path = _write(recs)
        try:
            md = render([path])
        finally:
            os.unlink(path)
        self.assertIn("mixed", md.lower())


if __name__ == "__main__":
    unittest.main()
