"""Utilization metrics (observed, deterministic).

IMPORTANT SCOPING NOTE (surfaced in every response):
  Public aviation data does NOT directly observe unmet demand — passengers
  who wanted to fly but could not obtain a seat are never counted anywhere.
  This module therefore reports only OBSERVED utilization:
    - load factor (passengers / available seats)
    - year-over-year change in load factor ("utilization trend")
    - passengers per performed departure

  Rising load factor + rising demand is the closest honest indicator that
  demand may be outpacing offered capacity, but it is an indicator, not a
  measurement of unmet demand.
"""
from __future__ import annotations

UNMET_DEMAND_NOTE = (
    "Public data does not directly measure unmet demand (travellers unable to "
    "obtain a seat). Values here are observed utilization indicators only: "
    "load factor, its year-over-year change, and passengers per departure."
)


def utilization_metrics(yearly: dict[int, dict]) -> dict:
    years = sorted(yearly.keys())
    if not years:
        return {"error": "no data"}
    end = years[-1]
    prev = years[-2] if len(years) >= 2 else None

    t_end = yearly[end]
    lf_end = t_end["passengers"] / t_end["seats"] if t_end["seats"] else None
    pax_per_dep = (
        t_end["passengers"] / t_end["departures_performed"]
        if t_end["departures_performed"] else None
    )

    result = {
        "year": end,
        "load_factor": None if lf_end is None else round(lf_end, 4),
        "load_factor_pct": None if lf_end is None else round(lf_end * 100, 1),
        "passengers_per_departure": None if pax_per_dep is None else round(pax_per_dep, 1),
        "utilization_trend_points": None,
        "prior_year": prev,
        "prior_year_load_factor": None,
        "note": UNMET_DEMAND_NOTE,
    }

    if prev is not None:
        t_prev = yearly[prev]
        lf_prev = t_prev["passengers"] / t_prev["seats"] if t_prev["seats"] else None
        if lf_prev is not None and lf_end is not None:
            delta = (lf_end - lf_prev) * 100.0
            result["utilization_trend_points"] = round(delta, 2)
            result["prior_year_load_factor"] = round(lf_prev, 4)
    return result
