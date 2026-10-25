import isolated_env  # noqa: F401  (must precede app imports)
import unittest

from app.ml.reference_training import (
    REFERENCE_FEATURES,
    TARGET_COLUMN,
    build_reference_donor_frame,
    build_shortage_stats,
    calibrate_cbsri_weights,
    load_reference_tables,
)


class ReferenceTrainingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.stock, cls.donors, cls.notifications = load_reference_tables()
        cls.frame = build_reference_donor_frame(cls.donors, cls.notifications)

    def test_one_row_per_notification_with_leakage_free_history(self) -> None:
        self.assertEqual(len(self.frame), len(self.notifications))
        self.assertEqual(tuple(c for c in self.frame.columns if c not in ("invitation_date", TARGET_COLUMN)), REFERENCE_FEATURES)
        self.assertEqual(set(self.frame[TARGET_COLUMN].unique()), {0, 1})
        # Prior-only aggregates: first notification of every donor has no history.
        self.assertTrue((self.frame.loc[self.frame["previous_requests"] == 0, "previous_responses"] == 0).all())
        self.assertTrue(((self.frame["previous_responses"] <= self.frame["previous_requests"]).all()))
        self.assertTrue((self.frame["response_rate"] <= 1.0).all())

    def test_shortage_stats_cover_all_blood_groups(self) -> None:
        stats = build_shortage_stats(self.stock)
        self.assertEqual(
            set(stats["blood_groups"]),
            {"A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"},
        )
        for group_stats in stats["blood_groups"].values():
            self.assertGreater(group_stats["avg_daily_demand"], 0)
            self.assertIn("closing_trend_per_day", group_stats)
            self.assertIn("seasonal_demand_factor_by_month", group_stats)

    def test_calibrated_weights_are_normalized(self) -> None:
        calibration = calibrate_cbsri_weights(self.frame, self.stock)
        weights = calibration["weights"]
        self.assertAlmostEqual(sum(weights.values()), 1.0, places=3)
        self.assertTrue(all(value >= 0 for value in weights.values()))


if __name__ == "__main__":
    unittest.main()
