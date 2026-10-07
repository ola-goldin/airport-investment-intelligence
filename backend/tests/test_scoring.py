"""Unit tests for the deterministic scoring engine (plan Rule 8: reproducible)."""
import math

import pytest

from app.analytics.scoring import (
    COMPONENT_ORDER,
    ScoringModel,
    compute_score,
    load_scoring_model,
    normalize_component,
)


@pytest.fixture(scope="module")
def model() -> ScoringModel:
    return load_scoring_model()


def test_weights_sum_to_one(model):
    assert abs(sum(model.weights.values()) - 1.0) < 1e-9


def test_all_components_present_in_config(model):
    for key in COMPONENT_ORDER:
        assert key in model.weights


def test_invalid_weights_rejected(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "scoring_model:\n"
        "  version: 'bad'\n"
        "  analysis_window_years: 3\n"
        "  long_haul_threshold_miles: 3000\n"
        "  weights:\n"
        "    demand_growth: 0.5\n"
        "    load_factor: 0.5\n"
        "    utilization_trend: 0.5\n"
        "    flight_growth: 0.5\n"
        "    long_haul: 0.5\n"
        "  normalization:\n"
        "    growth_pct_cap: 15.0\n"
        "    load_factor_floor: 0.65\n"
        "    load_factor_ceiling: 0.9\n"
        "    utilization_trend_range_points: 5.0\n"
        "    long_haul_share_cap: 0.3\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_scoring_model(bad)


def test_normalize_growth_cap(model):
    # 15% growth -> 100 pts (cap), 7.5% -> 50
    assert normalize_component("demand_growth", 0.15, model) == 100.0
    assert math.isclose(normalize_component("demand_growth", 0.075, model), 50.0)


def test_normalize_load_factor(model):
    n = model.normalization
    assert normalize_component("load_factor", n["load_factor_floor"], model) == 0.0
    assert normalize_component("load_factor", n["load_factor_ceiling"], model) == 100.0


def test_normalize_utilization_trend_center(model):
    # zero change -> neutral 50
    assert normalize_component("utilization_trend", 0.0, model) == 50.0
    assert normalize_component("utilization_trend", 5.0, model) == 100.0
    assert normalize_component("utilization_trend", -5.0, model) == 0.0


def test_score_known_values(model):
    raw: dict[str, float | None] = {
        "demand_growth": 0.15,        # 100
        "load_factor": 0.90,          # 100
        "utilization_trend": 5.0,     # 100
        "flight_growth": 0.15,        # 100
        "long_haul": 0.30,            # 100
    }
    result = compute_score(raw, model)
    assert result["score"] == 100.0
    assert not result["weights_renormalized"]


def test_score_zero_values(model):
    raw: dict[str, float | None] = {
        "demand_growth": 0.0,
        "load_factor": model.normalization["load_factor_floor"],
        "utilization_trend": -5.0,
        "flight_growth": 0.0,
        "long_haul": 0.0,
    }
    result = compute_score(raw, model)
    assert result["score"] == 0.0


def test_score_midpoint(model):
    raw: dict[str, float | None] = {
        "demand_growth": 0.075,   # 50
        "load_factor": (0.65 + 0.90) / 2,  # 50
        "utilization_trend": 0.0,  # 50
        "flight_growth": 0.075,   # 50
        "long_haul": 0.15,        # 50
    }
    result = compute_score(raw, model)
    assert math.isclose(result["score"], 50.0)


def test_missing_component_renormalizes(model):
    full: dict[str, float | None] = {
        "demand_growth": 0.075,
        "load_factor": 0.775,
        "utilization_trend": 0.0,
        "flight_growth": 0.075,
        "long_haul": 0.15,
    }
    without_lh: dict[str, float | None] = {k: v for k, v in full.items() if k != "long_haul"}
    result = compute_score(without_lh, model)
    assert "long_haul" in result["missing_components"]
    assert result["weights_renormalized"] is True
    # midpoint values renormalized over 4 components still yield 50
    assert math.isclose(result["score"], 50.0)
    used = {c["key"]: c["weight_used"] for c in result["components"]}
    assert math.isclose(sum(used.values()), 1.0, abs_tol=1e-6)
    assert math.isclose(used["demand_growth"], model.weights["demand_growth"] / 0.90, abs_tol=1e-3)


def test_all_missing_raises(model):
    with pytest.raises(ValueError):
        compute_score({"demand_growth": None}, model)
