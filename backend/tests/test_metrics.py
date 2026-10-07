"""Tests for demand growth, utilization and metric orchestration."""
import math

from app.analytics.demand import cagr, growth_metrics
from app.analytics.metrics import compare_airports, get_airport_metrics, rank_airports
from app.analytics.utilization import utilization_metrics
from app.runtime import get_runtime


def test_cagr():
    growth = cagr(100.0, 121.0, 2)
    assert growth is not None
    assert math.isclose(growth, 0.10, rel_tol=1e-9)
    assert cagr(0, 100, 2) is None
    assert cagr(100, 50, 0) is None


def _yearly():
    return {
        2021: {"passengers": 1000, "seats": 1200, "departures_scheduled": 100,
               "departures_performed": 98, "long_haul_departures": 10, "long_haul_seats": 150},
        2022: {"passengers": 1100, "seats": 1250, "departures_scheduled": 105,
               "departures_performed": 103, "long_haul_departures": 12, "long_haul_seats": 180},
        2023: {"passengers": 1210, "seats": 1300, "departures_scheduled": 110,
               "departures_performed": 108, "long_haul_departures": 13, "long_haul_seats": 200},
    }


def test_growth_metrics_window():
    g = growth_metrics(_yearly(), 3)
    assert g["window"] == {"start": 2021, "end": 2023, "years": 3}
    assert g["demand_growth_pct"] == 10.0
    assert math.isclose(g["flight_growth_pct"], 4.88, rel_tol=1e-2)


def test_utilization_metrics():
    u = utilization_metrics(_yearly())
    assert u["year"] == 2023
    assert u["prior_year"] == 2022
    assert math.isclose(u["load_factor"], round(1210 / 1300, 4), abs_tol=1e-9)
    assert math.isclose(
        u["utilization_trend_points"],
        round((1210 / 1300 - 1100 / 1250) * 100, 2),
        abs_tol=1e-9,
    )
    assert "does not directly measure unmet demand" in u["note"]


def test_full_metrics_for_bos():
    repo, model = get_runtime()
    m = get_airport_metrics(repo, model, "BOS")
    assert m["airport"] == "BOS"
    assert 0 <= m["scoring"]["score"] <= 100
    assert len(m["scoring"]["components"]) == 5
    assert not m["scoring"]["weights_renormalized"]
    assert any("Analysis window" in a for a in m["assumptions"])
    # load factor must equal passengers/seats
    assert m["metrics"]["load_factor"] == round(
        m["metrics"]["passengers"] / m["metrics"]["seats"], 4
    )


def test_long_haul_definition_and_values():
    repo, model = get_runtime()
    m = get_airport_metrics(repo, model, "ANC")
    share = m["metrics"]["long_haul_departures_share"]
    assert share is not None
    t = repo.totals("ANC", m["data_year"])
    assert t is not None
    assert m["metrics"]["long_haul_departures_share"] == round(
        t["long_haul_departures"] / t["departures_performed"], 4
    )


def test_unknown_airport_error():
    repo, model = get_runtime()
    assert "error" in get_airport_metrics(repo, model, "ZZZ")


def test_spec_named_tool_aliases():
    """The spec vocabulary (calculate_long_haul_share, calculate_capacity_pressure)
    must resolve to the same deterministic implementations."""
    from app.analytics import metrics as m

    assert m.calculate_long_haul_share is m.long_haul_share
    assert m.calculate_capacity_pressure is m.utilization_analysis
    repo, model = get_runtime()
    lh = m.calculate_long_haul_share(repo, "ANC", repo.latest_year())
    assert "long_haul_departures_share" in lh
    cp = m.calculate_capacity_pressure(repo, model, "SFO")
    assert "does not directly measure unmet demand" in cp["note"]


def test_rank_new_england_only_ne_states():
    repo, model = get_runtime()
    r = rank_airports(repo, model, "New England", limit=10)
    ne = {"CT", "ME", "MA", "NH", "RI", "VT"}
    assert r["ranking"], "ranking must not be empty"
    for entry in r["ranking"]:
        assert entry["state"] in ne
    scores = [e["score"] for e in r["ranking"]]
    assert scores == sorted(scores, reverse=True)


def test_compare_two_airports():
    repo, model = get_runtime()
    c = compare_airports(repo, model, ["LAX", "SNA"])
    codes = [m["airport"] for m in c["comparison"]]
    assert codes == ["LAX", "SNA"]
    assert c["pairwise_summary"] is not None
    rows = c["pairwise_summary"]["rows"]
    by_metric = {r["metric"]: r for r in rows}
    la_row = by_metric["Load factor"]
    assert set(la_row.keys()) >= {"LAX", "SNA", "higher", "metric"}
