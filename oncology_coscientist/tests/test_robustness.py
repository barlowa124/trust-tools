"""Robustness battery: transcript replay integrity, check boundaries,
and survival-metric edge cases."""

import numpy as np
import pandas as pd
import pytest

from oncocs.checks import (check_convergence, check_min_events,
                           check_split_integrity)
from oncocs.llm.recorded import (RecordedBackend, RecordingBackend,
                                 ScriptedBackend, TranscriptMismatch,
                                 _prompt_sha)
from oncocs.splits import split_sha256


class TestReplayIntegrity:
    def test_prompt_mismatch_raises(self):
        rec = [{"index": 0, "model_id": "m",
                "prompt_sha256": _prompt_sha([{"role": "user",
                                             "content": "orig"}]),
                "response": "ok"}]
        rb = RecordedBackend(rec)
        with pytest.raises(TranscriptMismatch, match="mismatch"):
            rb.complete([{"role": "user", "content": "CHANGED"}])

    def test_replay_exhaustion_raises(self):
        rec = [{"index": 0, "model_id": "m",
                "prompt_sha256": _prompt_sha([{"role": "u", "content": "a"}]),
                "response": "r"}]
        rb = RecordedBackend(rec)
        rb.complete([{"role": "u", "content": "a"}])
        with pytest.raises(TranscriptMismatch, match="exhausted"):
            rb.complete([{"role": "u", "content": "a"}])

    def test_recorded_empty_transcript(self):
        rb = RecordedBackend([])
        assert rb.model_id == "recorded"
        with pytest.raises(TranscriptMismatch):
            rb.complete([{"role": "u", "content": "x"}])

    def test_recording_then_replay_roundtrip(self):
        inner = ScriptedBackend(["ans1", "ans2"])
        rec = RecordingBackend(inner)
        msgs = [{"role": "u", "content": "q1"}]
        assert rec.complete(msgs) == "ans1"
        assert len(rec.transcript) == 1
        rb = RecordedBackend(rec.transcript)
        assert rb.complete(msgs) == "ans1"  # same prompt replays

    def test_prompt_sha_order_insensitive_but_content_sensitive(self):
        a = _prompt_sha([{"content": "x", "role": "u"}])
        b = _prompt_sha([{"role": "u", "content": "x"}])
        c = _prompt_sha([{"role": "u", "content": "y"}])
        assert a == b and a != c


class TestCheckBoundaries:
    def _split(self, tr, te):
        return {"train_ids": tr, "test_ids": te,
                "split_sha256": split_sha256(tr, te)}

    def test_split_integrity_overlap_fails(self):
        s = self._split(["p1", "p2"], ["p2", "p3"])
        r = check_split_integrity(s, ["p1", "p2", "p3"])
        assert not r["passed"] and r["detail"]["overlap_count"] == 1

    def test_split_integrity_tampered_hash_fails(self):
        s = self._split(["p1"], ["p2"])
        s["split_sha256"] = "0" * 64
        r = check_split_integrity(s, ["p1", "p2"])
        assert not r["passed"] and not r["detail"]["hash_match"]

    def test_split_integrity_missing_ids_fraction(self):
        tr = [f"t{i}" for i in range(50)]
        te = [f"v{i}" for i in range(50)]
        # 2 missing of 100 -> 2% > 1% tolerance -> fail
        s = self._split(tr + ["ghost1", "ghost2"], te)
        r = check_split_integrity(s, tr + te)
        assert not r["passed"]

    def test_min_events_boundary(self):
        tr = pd.Series([1] * 30 + [0] * 30)
        te = pd.Series([1] * 10 + [0] * 10)
        assert check_min_events(tr, te)["passed"]
        te_low = pd.Series([1] * 9 + [0] * 11)
        assert not check_min_events(tr, te_low)["passed"]

    def test_convergence_on_stub(self):
        class FakeCph:
            log_likelihood_ = -100.0
            params_ = pd.Series([0.1, -0.2])
        assert check_convergence(FakeCph())["passed"]

        class BadCph:
            log_likelihood_ = float("nan")
            params_ = pd.Series([0.1])
        assert not check_convergence(BadCph())["passed"]


class TestMetricsEdges:
    def _surv(self, n=50, seed=0):
        from sksurv.util import Surv
        rng = np.random.RandomState(seed)
        return Surv.from_arrays(rng.rand(n) < 0.6,
                                rng.rand(n) * 40 + 1)

    def test_td_auc_all_test_times_below_eval_window(self):
        from oncocs.models.metrics import td_auc
        yt, ye = self._surv(), self._surv(seed=1)
        # test max time < smallest eval month -> empty dict, not crash
        ye["time"][:] = np.clip(ye["time"], None, 10)
        out = td_auc(yt, ye, np.random.RandomState(2).randn(50),
                     eval_months=(12, 24, 36))
        assert out == {}

    def test_calibration_constant_predictions(self):
        from oncocs.models.metrics import calibration_24m
        yt = self._surv()
        grid = np.linspace(1, 60, 100)
        surv = np.tile(np.linspace(0.9, 0.1, 100), (50, 1))
        rows = calibration_24m(yt, surv, grid, t=24.0)
        # constant predicted S(24) -> single bucket, not qcut crash
        assert len(rows) == 1 and rows[0]["n"] == 50

    def test_scripted_backend_overrun_repeats_last(self):
        b = ScriptedBackend(["a", "b"])
        assert b.complete([]) == "a"
        assert b.complete([]) == "b"
        assert b.complete([]) == "b"  # clamps, no IndexError
