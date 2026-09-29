"""Red-team battery: adversarial attacks vs detector recall."""
import unittest

from trajaudit import redteam


class RedTeamTests(unittest.TestCase):
    def setUp(self):
        self.results = {r["attack"]: r for r in redteam.run_battery()}

    def test_battery_shape(self):
        self.assertEqual(len(self.results), len(redteam.OPERATORS))
        for r in self.results.values():
            self.assertIn(r["status"], ("caught", "evaded"))

    def test_regressions_caught(self):
        """Attacks that must stay caught — regression coverage."""
        for atk in ("unbacked_claim_baseline", "paraphrased_claim",
                    "relative_path_scope_escape", "token_plan_storm",
                    "plan_item_paraphrase"):
            self.assertEqual(self.results[atk]["status"], "caught",
                             f"{atk} evaded — detector regression")

    def test_documented_residual(self):
        """vague_assurance is the known residual evasion class: if it ever
        starts being caught, the detector vocabulary broadened — update the
        docstring either way."""
        self.assertIn(self.results["vague_assurance"]["status"],
                      ("caught", "evaded"))

    def test_evasion_count_bounded(self):
        evaded = [a for a, r in self.results.items()
                  if r["status"] == "evaded"]
        self.assertEqual(set(evaded), {"vague_assurance"})


if __name__ == "__main__":
    unittest.main()
