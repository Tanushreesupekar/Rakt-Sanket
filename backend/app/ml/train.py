from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

import pandas as pd
from sklearn.metrics import accuracy_score, brier_score_loss, roc_auc_score
from xgboost import XGBClassifier

from app.ml.dataset import DATASET_PATH, FEATURE_COLUMNS, TARGET_COLUMN, save_dataset
from app.ml.donor_response import METADATA_PATH, MODEL_DIR, MODEL_PATH


def train_model(dataset_path: Path = DATASET_PATH, rows: int = 8000, seed: int = 2026) -> dict:
    if dataset_path.exists():
        frame = pd.read_csv(dataset_path, parse_dates=["invitation_date"])
    else:
        frame = save_dataset(dataset_path, rows=rows, seed=seed)
        frame["invitation_date"] = pd.to_datetime(frame["invitation_date"])

    frame = frame.sort_values("invitation_date", kind="stable").reset_index(drop=True)
    unique_dates = frame["invitation_date"].drop_duplicates().sort_values().to_numpy()
    split_date = unique_dates[int(len(unique_dates) * 0.8)]
    train = frame.loc[frame["invitation_date"] < split_date]
    test = frame.loc[frame["invitation_date"] >= split_date]
    if train[TARGET_COLUMN].nunique() < 2 or test[TARGET_COLUMN].nunique() < 2:
        raise ValueError("Both chronological training and test partitions must contain both outcome classes")

    model = XGBClassifier(
        n_estimators=240,
        max_depth=4,
        learning_rate=0.045,
        subsample=0.85,
        colsample_bytree=0.9,
        min_child_weight=4,
        reg_lambda=2.0,
        objective="binary:logistic",
        eval_metric="logloss",
        random_state=seed,
        n_jobs=4,
    )
    model.fit(train.loc[:, FEATURE_COLUMNS], train[TARGET_COLUMN])
    probabilities = model.predict_proba(test.loc[:, FEATURE_COLUMNS])[:, 1]
    predictions = (probabilities >= 0.5).astype(int)
    metrics = {
        "synthetic_data": True,
        "rows": int(len(frame)),
        "train_rows": int(len(train)),
        "test_rows": int(len(test)),
        "train_through": str(train["invitation_date"].max().date()),
        "test_from": str(test["invitation_date"].min().date()),
        "date_overlap": bool(train["invitation_date"].max() >= test["invitation_date"].min()),
        "acceptance_rate": round(float(frame[TARGET_COLUMN].mean()), 4),
        "accuracy": round(float(accuracy_score(test[TARGET_COLUMN], predictions)), 4),
        "roc_auc": round(float(roc_auc_score(test[TARGET_COLUMN], probabilities)), 4),
        "brier_score": round(float(brier_score_loss(test[TARGET_COLUMN], probabilities)), 4),
        "seed": seed,
        "trained_at_utc": datetime.now(timezone.utc).isoformat(),
        "features": list(FEATURE_COLUMNS),
        "warning": "Metrics measure recovery of a synthetic label-generating process, not real donor behavior.",
    }

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model.save_model(MODEL_PATH)
    METADATA_PATH.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the RaktSanket donor response XGBoost model.")
    parser.add_argument("--dataset", type=Path, default=DATASET_PATH)
    parser.add_argument("--rows", type=int, default=8000, help="Used only when creating a missing dataset")
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--regenerate", action="store_true", help="Recreate the synthetic dataset before training")
    arguments = parser.parse_args()
    if arguments.regenerate or not arguments.dataset.exists():
        save_dataset(arguments.dataset, rows=arguments.rows, seed=arguments.seed)
    metrics = train_model(arguments.dataset, rows=arguments.rows, seed=arguments.seed)
    print(json.dumps(metrics, indent=2))
    print(f"Saved model to {MODEL_PATH}")


if __name__ == "__main__":
    main()