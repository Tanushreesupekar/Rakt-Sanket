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


if __name__ == "__main__":
    unittest.main()