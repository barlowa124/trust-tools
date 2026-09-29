"""evalh core: graders, task loading, chained run records, verify."""
import copy
import json
import os
import tempfile
import unittest

from evalh import chainfmt
from evalh.graders import grade, is_degenerate
from evalh.runner import check_log, run
from evalh.sweep import sweep, sweep_table
from evalh.tasks import load_tasks

TASKS = [
    {"id": "t1", "prompt": "what organ clears X?",
     "grader": {"kind": "contains", "value": "liver"}, "tag": "answerable"},
    {"id": "t2", "prompt": "what clears Y?",
     "grader": {"kind": "abstain"}, "tag": "unanswerable"},
    {"id": "t3", "prompt": "say PONG",
     "grader": {"kind": "regex", "value": "^PONG"}, "tag": "format"},
]


def _spec(tasks=None, **kw):
    f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
    json.dump(tasks if tasks is not None else TASKS, f)
    f.close()
    return f.name


class TaskTests(unittest.TestCase):
    def test_loads_and_validates(self):
        ts = load_tasks(_spec())
        self.assertEqual(len(ts), 3)

    def test_rejects_missing_grader(self):
        bad = [{"id": "x", "prompt": "p", "tag": "t"}]
        with self.assertRaises(ValueError):
            load_tasks(_spec(bad))

    def test_rejects_dup_ids(self):
        bad = TASKS + [dict(TASKS[0])]
        with self.assertRaises(ValueError):
            load_tasks(_spec(bad))


class GraderTests(unittest.TestCase):
    def test_contains_word_boundary(self):
        g = {"kind": "contains", "value": "62"}
        self.assertEqual(grade("it is 620", g)["score"], 0.0)
        self.assertEqual(grade("it is 62 today", g)["score"], 1.0)

    def test_abstain(self):
        g = {"kind": "abstain"}
        self.assertEqual(grade("I don't have enough information to answer.",
                               g)["label"], "abstains")
        self.assertEqual(grade("the answer is kidney", g)["label"], "answers")

    def test_not_contains(self):
        g = {"kind": "not_contains", "value": "oops"}
        self.assertEqual(grade("clean output", g)["score"], 1.0)
        self.assertEqual(grade("oops failed", g)["score"], 0.0)

    def test_degenerate_detected(self):
        self.assertTrue(is_degenerate("the the the the the"))
        self.assertFalse(is_degenerate("the liver clears it"))


class RunTests(unittest.TestCase):
    def _gen(self, prompt):
        if "clears X" in prompt:
            return "liver"
        if "clears Y" in prompt:
            return "I don't have enough information to answer."
        return "PONG"

    def test_run_chains_and_scores(self):
        recs, summ = run(TASKS, self._gen, {"name": "fake"})
        self.assertEqual(len(recs), 3)
        self.assertEqual(recs[0]["chain_prev"], "genesis")
        self.assertEqual(recs[1]["chain_prev"], recs[0]["result_id"])
        self.assertAlmostEqual(summ["score"], 1.0)
        self.assertEqual(check_log(recs), [])

    def test_grades_reflected(self):
        def bad_gen(p):
            return "kidney"
        recs, summ = run(TASKS, bad_gen, {"name": "fake"})
        self.assertEqual(recs[0]["grade"]["label"], "fail")
        self.assertEqual(recs[1]["grade"]["label"], "answers")
        self.assertLess(summ["score"], 1.0)

    def test_tamper_and_reorder_detected(self):
        recs, _ = run(TASKS, self._gen, {"name": "fake"})
        tam = copy.deepcopy(recs)
        tam[1]["output"]["text"] = "forged"
        self.assertTrue(any("hash" in p for p in check_log(tam)))
        reord = [recs[1], recs[0], recs[2]]
        self.assertTrue(any("chain" in p for p in check_log(reord)))

    def test_sweep_stage_table(self):
        def good(p):
            return "PONG" if "PONG" in p else ("liver" if "X" in p else
                                             "I don't have enough information to answer.")
        def collapsed(p):
            return "yes yes yes yes yes"
        recs, summ = sweep([("sft", good, {"name": "sft"}),
                            ("dpo", collapsed, {"name": "dpo"})],
                           TASKS)
        tbl = sweep_table(summ)
        self.assertIn("| sft |", tbl)
        self.assertIn("| dpo |", tbl)
        self.assertEqual(summ["stages"][0]["score"], 1.0)
        self.assertLess(summ["stages"][1]["score"], 1.0)


if __name__ == "__main__":
    unittest.main()
