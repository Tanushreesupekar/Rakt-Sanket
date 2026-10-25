"""Blood shortage forecaster (SFS): history-calibrated time-series projection.

Dynamics (per blood group, per district inventory row):
  demand(day) = avg_daily_demand * weekday_factor * seasonal_factor(group, month)
  net_outflow(day) = demand(day) - expected_collections(day)
  expected_collections(day) = demand(day) * collection_coverage(group)

where collection_coverage and seasonal factors come from the linked
reference tables (blood_stock_demand_full.csv) when
models/shortage_forecast.json exists. All history terms are scale-free
ratios, so operator-edited inventory levels keep their own scale.
Without the artifact, the forecaster falls back to the original
weekday-adjusted demand baseline.

SHAP-style transparency: each forecast point carries the seasonal factor,
collection offset, trend direction, and unmet-demand base rate behind it,
and the group explanation names the dominant pressure. The underlying
XGBoost-trend terminology is avoided: this is a transparent statistical
forecaster (moving-average demand + seasonal multipliers + collection
offset), not ARIMA/SARIMA/Prophet. Model limitations are documented in
the explanation strings and in reference_training.py.
"""
from __future__ import annotations

from datetime import date, timedelta
from functools import lru_cache
import json
from pathlib import Path

from app.models import Inventory
from app.services.scoring import risk_label


WEEKDAY_FACTORS = (0.96, 0.98, 1.00, 1.02, 1.04, 1.12, 1.08)
FESTIVAL_MONTHS = (1, 8, 10, 11)
STATS_PATH = Path(__file__).resolve().parents[2] / "models" / "shortage_forecast.json"


@lru_cache(maxsize=1)
def load_shortage_stats() -> dict:
    if not STATS_PATH.exists():
        return {"blood_groups": {}}
    try:
        return json.loads(STATS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"blood_groups": {}}


def group_stats(blood_group: str) -> dict:
    return load_shortage_stats().get("blood_groups", {}).get(blood_group, {})


def build_forecast(inventory: Inventory, horizon_days: int = 14) -> list[dict]:
    stats = group_stats(inventory.blood_group)
    coverage = stats.get("avg_collected", 0) / max(1e-9, stats.get("avg_daily_demand", 0)) if stats.get("avg_daily_demand") else 0.0
    coverage = min(0.9, max(0.0, coverage))
    seasonal_map = stats.get("seasonal_demand_factor_by_month", {})
    trend = float(stats.get("closing_trend_per_day", 0.0))
    trend_label = "Decreasing" if trend < -0.005 else ("Increasing" if trend > 0.005 else "Stable")
    unmet_rate = stats.get("unmet_rate")

    projected = float(inventory.units_available)
    points = []
    for offset in range(1, horizon_days + 1):
        forecast_date = date.today() + timedelta(days=offset)
        weekday_factor = WEEKDAY_FACTORS[forecast_date.weekday()]
        seasonal_factor = float(seasonal_map.get(str(forecast_date.month), 1.0))
        seasonal_factor = min(1.5, max(0.5, seasonal_factor))
        demand = inventory.avg_daily_demand * weekday_factor * seasonal_factor
        collected = demand * coverage
        projected = max(0.0, projected - (demand - collected))
        risk = min(100.0, max(0.0, (inventory.safety_stock_units - projected) / max(1, inventory.safety_stock_units) * 100))
        points.append({
            "date": forecast_date,
            "projected_units": round(projected, 1),
            "demand_units": round(demand, 1),
            "shortage_score": round(risk, 1),
            "risk_level": risk_label(risk),
            "explanation": _explain(
                projected, inventory.safety_stock_units, offset,
                seasonal_factor, coverage, trend_label, unmet_rate,
                bool(stats),
            ),
        })
    return points


def shortage_score(inventory: Inventory, horizon_days: int) -> float:
    point = build_forecast(inventory, horizon_days)[-1]
    return point["shortage_score"]


def _explain(
    projected: float,
    safety_stock: int,
    days: int,
    seasonal_factor: float = 1.0,
    coverage: float = 0.0,
    trend_label: str = "Stable",
    unmet_rate: float | None = None,
    history_used: bool = False,
) -> str:
    if projected < safety_stock:
        base = f"Projected stock falls below the {safety_stock}-unit safety level within {days} days."
    else:
        base = f"Projected stock remains above the {safety_stock}-unit safety level over {days} days."
    if not history_used:
        return base + " Weekday-adjusted demand baseline (no reference history loaded)."
    parts = [
        f"Seasonal demand x{seasonal_factor:.2f}",
        f"collection coverage {coverage:.0%}",
        f"stock trend {trend_label}",
    ]
    if unmet_rate is not None:
        parts.append(f"historical unmet-demand rate {unmet_rate:.0%}")
    return base + " History signals: " + "; ".join(parts) + "."
