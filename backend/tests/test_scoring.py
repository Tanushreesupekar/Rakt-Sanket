import unittest

from app.services.scoring import CBSRIWeights, compute_cbsri, donor_priority, fatigue_multiplier, risk_label


class ScoringTests(unittest.TestCase):
    def test_default_weights_are_normalized_and_transparent(self) -> None:
        self.assertEqual(compute_cbsri(100, 100, 100), 100)
        self.assertEqual(compute_cbsri(0, 0, 0), 0)

    def test_fatigue_reduces_priority_and_recent_contact_counts_more(self) -> None:
        fresh = donor_priority(0.8, 0, None)
        repeatedly_contacted = donor_priority(0.8, 4, 2)
        self.assertGreater(fresh, repeatedly_contacted)
        self.assertLessEqual(fatigue_multiplier(8, 0), 0.15)

    def test_weights_normalize_and_risk_bands_are_stable(self) -> None:
        weights = CBSRIWeights(shortage=2, response=1, fatigue_adjusted_priority=1)
        self.assertEqual(compute_cbsri(100, 0, 0, weights), 50)
        self.assertEqual(risk_label(70), "critical")
        self.assertEqual(risk_label(45), "elevated")
        self.assertEqual(risk_label(44.99), "stable")

    def test_rejects_out_of_range_scores(self) -> None:
        with self.assertRaises(ValueError):
            compute_cbsri(101, 30, 30)
        with self.assertRaises(ValueError):
            donor_priority(1.1, 0, None)


if __name__ == "__main__":
    unittest.main()
