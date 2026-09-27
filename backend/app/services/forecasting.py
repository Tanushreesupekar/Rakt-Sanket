from datetime import date, timedelta

from app.models import Inventory
from app.services.scoring import risk_label


WEEKDAY_FACTORS = (0.96, 0.98, 1.00, 1.02, 1.04, 1.12, 1.08)


def build_forecast(inventory: Inventory, horizon_days: int = 14) -> list[dict]:
    projected = float(inventory.units_available)
    points = []
    for offset in range(1, horizon_days + 1):
        forecast_date = date.today() + timedelta(days=offset)
        factor = WEEKDAY_FACTORS[forecast_date.weekday()]
        demand = inventory.avg_daily_demand * factor
        projected = max(0.0, projected - demand)
        risk = min(100.0, max(0.0, (inventory.safety_stock_units - projected) / max(1, inventory.safety_stock_units) * 100))
        points.append({
            "date": forecast_date,
            "projected_units": round(projected, 1),
            "demand_units": round(demand, 1),
            "shortage_score": round(risk, 1),
            "risk_level": risk_label(risk),
            "explanation": _explain(projected, inventory.safety_stock_units, offset),
        })
    return points


def shortage_score(inventory: Inventory, horizon_days: int) -> float:
    point = build_forecast(inventory, horizon_days)[-1]
    return point["shortage_score"]


def _explain(projected: float, safety_stock: int, days: int) -> str:
    if projected < safety_stock:
        return f"Projected stock falls below the {safety_stock}-unit safety level within {days} days."
    return f"Projected stock remains above the {safety_stock}-unit safety level over {days} days."
