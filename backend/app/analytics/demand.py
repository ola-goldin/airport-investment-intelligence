"""Demand growth metrics (observed, deterministic).

demand_growth   = passenger CAGR over the trailing analysis window
flight_growth   = scheduled-departure CAGR over the same window

CAGR over a window that spans multiple years (n years between endpoints):
    (v_last / v_first) ** (1/n) - 1
"""
from __future__ import annotations


def cagr(first: float, last: float, years_between: int) -> float | None:
    if years_between <= 0 or first is None or last is None or first <= 0 or last <= 0:
        return None
    return (last / first) ** (1.0 / years_between) - 1.0


def growth_metrics(yearly: dict[int, dict], window_years: int) -> dict:
    """Compute demand/flight growth over the trailing `window_years` window."""
    years = sorted(yearly.keys())
    if len(years) < 2:
        return {"demand_growth_pct": None, "flight_growth_pct": None,
                "window": {"start": None, "end": None},
                "note": "Insufficient years of data for growth calculation."}

    end = years[-1]
    start_candidates = [y for y in years if y <= end - window_years + 1]
    start = max(start_candidates) if start_candidates else years[0]

    p_first = yearly[start]["passengers"]
    p_last = yearly[end]["passengers"]
    d_first = yearly[start]["departures_scheduled"]
    d_last = yearly[end]["departures_scheduled"]
    span = end - start

    demand = cagr(p_first, p_last, span)
    flights = cagr(d_first, d_last, span)

    return {
        "demand_growth_pct": None if demand is None else round(demand * 100, 2),
        "flight_growth_pct": None if flights is None else round(flights * 100, 2),
        "window": {"start": start, "end": end, "years": span + 1},
        "note": "CAGR over trailing window; post-recovery windows reflect rebound growth.",
    }
