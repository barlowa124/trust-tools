"""Service tests — fake generate_fns, no model deps."""
import json
import unittest

from modelserve.service import Service


def echo(p):
    return "ECHO:" + p


def shadow_same(p):
    return "ECHO:" + p


def shadow_diff(p):
    return "SHADOW:" + p


def svc(**kw):
    s = Service(echo, {"name": "echo-v1"}, **kw)
    s.start()
    return s


class ServiceTests(unittest.TestCase):
    def test_infer_returns_receipt(self):
        s = svc()
        r = s.infer("hello")
        s.stop()
        self.assertEqual(r["output"]["text"], "ECHO:hello")
        self.assertEqual(r["kind"], "serve_response")
        self.assertEqual(r["model"]["name"], "echo-v1")
        self.assertTrue(r["response_id"].startswith("srv-"))
        self.assertEqual(r["chain_prev"], "genesis")

    def test_chain_links_across_requests(self):
        s = svc()
        s.infer("a")
        r2 = s.infer("b")
        s.stop()
        self.assertEqual(r2["chain_prev"], s.records[0]["response_id"])
        self.assertEqual(s.check_chain(), [])

    def test_tamper_detected(self):
        s = svc()
        s.infer("a")
        s.records[0]["output"]["text"] = "EDITED"
        s.stop()
        problems = s.check_chain()
        self.assertTrue(any("hash mismatch" in p or "chain break" in p
                            for p in problems))

    def test_batching_collects(self):
        s = svc(batch_size=4, batch_window_s=0.5)
        import threading
        ts = [threading.Thread(target=s.infer, args=(f"p{i}",))
              for i in range(8)]
        for t in ts:
            t.start()
        for t in ts:
            t.join(5)
        s.stop()
        self.assertEqual(len(s.records), 8)
        self.assertGreaterEqual(s.stats["batches"], 2)

    def test_shadow_agree(self):
        s = svc(shadow_fn=shadow_same, shadow_model={"name": "cand"},
                shadow_fraction=1.0)
        for i in range(5):
            s.infer(f"p{i}")
        s.stop()
        self.assertEqual(s.stats["shadow_runs"], 5)
        self.assertEqual(s.stats["shadow_agree"], 5)
        rep = s.report()
        self.assertEqual(rep["shadow"]["agree_rate"], 1.0)

    def test_shadow_divergence_recorded(self):
        s = svc(shadow_fn=shadow_diff, shadow_model={"name": "cand"},
                shadow_fraction=1.0)
        r = s.infer("x")
        s.stop()
        self.assertEqual(s.stats["shadow_diverge"], 1)
        self.assertFalse(r["shadow"]["agrees_with_primary"])
        self.assertEqual(r["shadow"]["model"]["name"], "cand")

    def test_shadow_fraction_zero_never_runs(self):
        s = svc(shadow_fn=shadow_diff, shadow_model={"name": "cand"},
                shadow_fraction=0.0)
        s.infer("x")
        s.stop()
        self.assertEqual(s.stats["shadow_runs"], 0)

    def test_report_shape(self):
        s = svc()
        s.infer("a")
        s.infer("b")
        s.stop()
        rep = s.report()
        self.assertEqual(rep["requests"], 2)
        self.assertIn("mean_latency_s", rep)
        self.assertIsNone(rep["shadow"])

    def test_queue_latency_recorded(self):
        s = svc()
        r = s.infer("x")
        s.stop()
        self.assertIn("queued_s", r)
        self.assertGreaterEqual(r["queued_s"], 0)

    def test_records_serialize(self):
        s = svc()
        s.infer("x")
        s.stop()
        json.dumps(s.records[0])  # must be JSON-clean for JSONL logs


if __name__ == "__main__":
    unittest.main()


class BenchTests(unittest.TestCase):
    def _slow_fn(self, ms=5):
        import time
        def gen(p):
            time.sleep(ms / 1000)
            return "out:" + p
        return gen

    def test_report_shape_and_chain(self):
        from modelserve.bench import run_bench
        rep = run_bench(self._slow_fn(), {"name": "stub"},
                        n_requests=40, concurrency=8, batch_size=4)
        self.assertEqual(rep["n_served"], 40)
        self.assertEqual(rep["n_errors"], 0)
        self.assertEqual(rep["chain_problems"], [])
        lat = rep["client_latency_s"]
        self.assertLessEqual(lat["p50"], lat["p95"])
        self.assertLessEqual(lat["p95"], lat["p99"])
        self.assertGreater(rep["throughput_rps"], 0)

    def test_batching_groups_requests(self):
        from modelserve.bench import run_bench
        single = run_bench(self._slow_fn(), {"name": "s"},
                           n_requests=30, concurrency=6, batch_size=1)
        batched = run_bench(self._slow_fn(), {"name": "s"},
                            n_requests=30, concurrency=6, batch_size=6)
        self.assertLess(batched["batches"], single["batches"])

    def test_pct(self):
        from modelserve.bench import pct
        self.assertEqual(pct([1, 2, 3], 50), 2)
        self.assertEqual(pct([1, 2, 3], 100), 3)
        self.assertAlmostEqual(pct([0, 10], 25), 2.5)
        self.assertEqual(pct([], 50), 0.0)

    def test_cli_bench_stub(self):
        import sys, types, tempfile, os
        mod = types.ModuleType("benchstub")
        mod.gen = self._slow_fn(1)
        sys.modules["benchstub"] = mod
        from modelserve.cli import main
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "b.json")
            rc = main(["bench", "--generate-fn", "benchstub:gen",
                       "--batch-sizes", "1,4", "--requests", "20",
                       "--concurrency", "4", "--out", out])
            self.assertEqual(rc, 0)
            reps = json.load(open(out))
            self.assertEqual(len(reps), 2)
            self.assertEqual(reps[0]["model"]["generate_fn"],
                             "benchstub:gen")
