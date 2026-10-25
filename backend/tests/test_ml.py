import isolated_env  # noqa: F401  (must precede app imports)
import unittest

import pandas as pd

from app.ml.dataset import FEATURE_COLUMNS, TARGET_COLUMN, generate_dataset
from app.ml.donor_response import build_features, model_status, predict_response


class DonorResponseModelTests(unittest.TestCase):
    def test_synthetic_dataset_is_reproducible_and_has_expected_schema(self) -> None:
        first = generate_dataset(rows=300, seed=19)
        second = generate_dataset(rows=300, seed=19)
        pd.testing.assert_frame_equal(first, second)
        self.assertEqual(tuple(column for column in first.columns if column not in ("invitation_date", TARGET_COLUMN)), FEATURE_COLUMNS)
        self.assertEqual(set(first[TARGET_COLUMN].unique()), {0, 1})

    def test_trained_model_returns_bounded_probability_and_factor_explanation(self) -> None:
        status = model_status()
        self.assertTrue(status["available"], "Train backend model before running tests")
        self.assertFalse(status["metrics"]["date_overlap"])
        features = build_features(
            age=34,
            days_since_last_donation=240,
            donations_count=5,
            response_rate=0.7,
            notifications_30d=1,
            days_since_last_contact=45,
        )
        result = predict_response(features)
        self.assertIsNotNone(result)
        probability, explanation = result
        self.assertGreaterEqual(probability, 0)
        self.assertLessEqual(probability, 1)
        self.assertIn("Model factors:", explanation)


class BatchRankingTests(unittest.TestCase):
    def test_batched_ranking_matches_ranking_each_donor_alone(self) -> None:
        from datetime import date, datetime, timedelta, timezone

        from app.models import Donor
        from app.services.ranking import rank_donor, rank_donors

        today = date.today()
        donors = [
            Donor(id=index + 1, name=f"Donor {index}", district="Amravati", blood_group="O+",
                  age=19 + index * 3, donations_count=index % 9, response_rate=round(0.1 + index * 0.06, 2),
                  notifications_30d=index % 5, available=index % 7 != 0,
                  last_donation_date=None if index == 3 else today - timedelta(days=30 + index * 23),
                  last_contact_at=None if index % 3 == 0 else datetime.now(timezone.utc) - timedelta(days=index * 4))
            for index in range(14)
        ]
        self.assertEqual(rank_donors(donors), [rank_donor(donor) for donor in donors])
        self.assertEqual(rank_donors([]), [])


if __name__ == "__main__":
    unittest.main()
