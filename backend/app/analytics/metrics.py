"""Metrics orchestration: repository -> observed KPIs -> deterministic score.

Every public function returns a structured dict containing:
  - observed metrics (from BTS-schema data),
  - the deterministic score decomposition,
  - explicit assumptions/scoping notes,
  - the data source actually used.
"""
from __future__ import annotations

from app.analytics.demand import growth_metrics
from app.analytics.scoring import ScoringModel, compute_score
from app.analytics.utilization import utilization_metrics
from app.data.loader import AirportDataRepository

DATA_SOURCE_NOTES = {
    "seed_calibrated": (
        "Bundled seed dataset (BTS T-100 schema, real-world calibrated, NOT live data). "
        "Set AIRPORT_AGENT_BTS_DOWNLOAD=1 to fetch authoritative BTS T-100 CSVs."
    ),
    "bts_t100_download": "Authoritative BTS T-100 market data, downloaded and cached locally.",
}

_threshold_state = {"long_haul_threshold_miles": 3000}


def set_long_haul_threshold(value: int) -> None:
    _threshold_state["long_haul_threshold_miles"] = value


def long_haul_share(repo: AirportDataRepository, code: str, year: int) -> dict:
    t = repo.totals(code, year)
    if not t or not t["departures_performed"]:
        return {"error": f"No data for {code} in {year}."}
    dep = t["departures_performed"]
    seats = t["seats"]
    return {
        "airport": code,
        "year": year,
        "long_haul_departures_share": round(t["long_haul_departures"] / dep, 4) if dep else None,
        "long_haul_seat_share": round(t["long_haul_seats"] / seats, 4) if seats else None,
        "total_departures_performed": dep,
        "long_haul_departures": t["long_haul_departures"],
        "total_seats": seats,
        "long_haul_seats": t["long_haul_seats"],
        "methodology": (
            f"Long-haul = nonstop segment distance >= {_threshold_state['long_haul_threshold_miles']} miles "
            "(nonstop stage length). Shares are computed from departing segments, "
            "not circle-trip itineraries."
        ),
    }


def get_airport_metrics(
    repo: AirportDataRepository,
    model: ScoringModel,
    code: str,
    end_year: int | None = None,
) -> dict:
    code = code.upper()
    profile = repo.profile(code)
    if profile is None:
        return {"error": f"Unknown airport code: {code}"}

    latest = repo.latest_year() if end_year is None else end_year
    yearly = repo.yearly_totals(code)
    totals = repo.totals(code, latest)
    if totals is None:
        return {"error": f"No data for {code} in {latest}."}

    set_long_haul_threshold(model.long_haul_threshold_miles)
    growth = growth_metrics(yearly, model.window_years)
    util = utilization_metrics(yearly)
    lh = long_haul_share(repo, code, latest)

    load_factor = totals["passengers"] / totals["seats"] if totals["seats"] else None
    raw_components: dict[str, float | None] = {
        "demand_growth": growth["demand_growth_pct"] / 100.0 if growth["demand_growth_pct"] is not None else None,
        "load_factor": load_factor,
        "utilization_trend": util["utilization_trend_points"],
        "flight_growth": growth["flight_growth_pct"] / 100.0 if growth["flight_growth_pct"] is not None else None,
        "long_haul": lh.get("long_haul_departures_share"),
    }
    scoring = compute_score(raw_components, model)

    return {
        "airport": code,
        "profile": profile,
        "data_year": latest,
        "metrics": {
            "passengers": totals["passengers"],
            "seats": totals["seats"],
            "departures_scheduled": totals["departures_scheduled"],
            "departures_performed": totals["departures_performed"],
            "load_factor": None if load_factor is None else round(load_factor, 4),
            "passenger_growth_pct": growth["demand_growth_pct"],
            "flight_growth_pct": growth["flight_growth_pct"],
            "growth_window": growth["window"],
            "utilization_trend_points": util["utilization_trend_points"],
            "long_haul_departures_share": lh.get("long_haul_departures_share"),
        },
        "scoring": scoring,
        "assumptions": build_assumptions(model, growth, util, repo),
        "data_source": repo.data_source,
        "data_source_note": DATA_SOURCE_NOTES.get(repo.data_source, repo.data_source),
    }


def rank_airports(
    repo: AirportDataRepository,
    model: ScoringModel,
    region: str,
    limit: int = 10,
) -> dict:
    from app.data.metadata import region_to_states  # local import avoids cycle

    states = region_to_states(region)
    if states is None:
        codes = repo.codes()
        scope = "United States"
    else:
        codes = repo.codes_in_states(states)
        scope = f"states {sorted(states)}"
    if not codes:
        return {"error": f"No airports found for region '{region}'."}

    entries = []
    for code in codes:
        m = get_airport_metrics(repo, model, code)
        if "error" in m:
            continue
        entries.append({
            "airport": m["airport"],
            "name": m["profile"]["name"],
            "city": m["profile"]["city"],
            "state": m["profile"]["state"],
            "score": m["scoring"]["score"],
            "passenger_growth_pct": m["metrics"]["passenger_growth_pct"],
            "load_factor": m["metrics"]["load_factor"],
            "utilization_trend_points": m["metrics"]["utilization_trend_points"],
        })
    entries.sort(key=lambda e: e["score"], reverse=True)
    return {
        "region": region,
        "scope": scope,
        "ranking": entries[:limit],
        "assumptions": [
            "Ranking uses the deterministic Expansion Opportunity Score "
            f"(model v{model.version}); see /scoring-model for weights.",
            "Higher score = stronger observed demand growth and utilization; "
            "it is not a prediction of investment returns.",
        ],
        "data_source": repo.data_source,
    }


def compare_airports(
    repo: AirportDataRepository,
    model: ScoringModel,
    codes: list[str],
) -> dict:
    results = []
    for code in codes:
        m = get_airport_metrics(repo, model, code)
        if "error" in m:
            results.append({"airport": code.upper(), "error": m["error"]})
        else:
            results.append(m)
    ok = [m for m in results if "error" not in m]
    summary = _pairwise_summary(ok[0], ok[1]) if len(ok) == 2 else None
    return {"comparison": results, "pairwise_summary": summary, "data_source": repo.data_source}


def _pairwise_summary(a: dict, b: dict) -> dict:
    fields = [
        ("score", "Investment score"),
        ("passenger_growth_pct", "Passenger growth %/yr"),
        ("flight_growth_pct", "Flight growth %/yr"),
        ("load_factor", "Load factor"),
        ("utilization_trend_points", "Utilization trend (LF pts YoY)"),
        ("long_haul_departures_share", "Long-haul share"),
    ]
    rows = []
    for key, label in fields:
        va = a["scoring"]["score"] if key == "score" else a["metrics"].get(key)
        vb = b["scoring"]["score"] if key == "score" else b["metrics"].get(key)
        if va is None or vb is None or va == vb:
            winner = "tie"
        else:
            winner = a["airport"] if va > vb else b["airport"]
        rows.append({"metric": label, a["airport"]: va, b["airport"]: vb, "higher": winner})
    return {"rows": rows}


def utilization_analysis(repo: AirportDataRepository, model: ScoringModel, code: str) -> dict:
    code = code.upper()
    if repo.profile(code) is None:
        return {"error": f"Unknown airport code: {code}"}
    yearly = repo.yearly_totals(code)
    util = utilization_metrics(yearly)
    if "error" in util:
        return util
    growth = growth_metrics(yearly, model.window_years)
    t = repo.totals(code, util["year"])
    util.update({
        "airport": code,
        "passengers": t["passengers"] if t else None,
        "demand_growth_pct": growth["demand_growth_pct"],
    })
    return util


def build_assumptions(model: ScoringModel, growth: dict, util: dict, repo: AirportDataRepository) -> list[str]:
    notes = [
        f"Analysis window: trailing {model.window_years} years "
        f"({growth['window'].get('start')}-{growth['window'].get('end')}); growth is CAGR.",
        f"Long-haul threshold: nonstop segments >= {model.long_haul_threshold_miles} miles.",
        "Utilization trend is the observed YoY change in load factor (percentage points).",
        "The score is a deterministic composite of observed metrics, not a prediction of returns.",
        DATA_SOURCE_NOTES.get(repo.data_source, repo.data_source),
    ]
    if util.get("utilization_trend_points") is None:
        notes.append("Utilization trend unavailable (insufficient years of data).")
    return notes


# ---------------------------------------------------------------------------
# Canonical tool names (implementation spec §10). These are aliases over the
# same deterministic implementations — useful for external tool definitions
# (Dify tools, tests, notebooks) that expect the spec vocabulary:
#   get_airport_metrics / compare_airports / rank_airports are already
#   spec-named; long-haul and capacity-pressure are aliased here.
# NOTE: "capacity pressure" is the *documented proxy name*; the function
# returns observed utilization indicators only and never a fabricated
# unmet-demand figure (see app/analytics/utilization.py).
calculate_long_haul_share = long_haul_share
calculate_capacity_pressure = utilization_analysis
