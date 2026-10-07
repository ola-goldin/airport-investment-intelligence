"""Deterministic scoring engine — the LLM never modifies this model.

Expansion Opportunity Score (0-100):

    Score = 0.30*demand_growth + 0.25*load_factor + 0.20*utilization_trend
          + 0.15*flight_growth + 0.10*long_haul

All weights live in config/scoring.yaml and are validated at load time.
Every component is an OBSERVED metric computed from the underlying data.
Missing components cause weight renormalization over available components
and are reported explicitly (never silently).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_PATH = ROOT / "config" / "scoring.yaml"

COMPONENT_ORDER = [
    "demand_growth",
    "load_factor",
    "utilization_trend",
    "flight_growth",
    "long_haul",
]

COMPONENT_LABELS = {
    "demand_growth": "Passenger demand growth (CAGR, analysis window)",
    "load_factor": "Load factor, latest year (observed passengers / seats)",
    "utilization_trend": "Utilization trend (observed YoY change in load factor, points)",
    "flight_growth": "Flight growth (scheduled departure CAGR, analysis window)",
    "long_haul": "Long-haul share (observed share of departures >= threshold miles)",
}


@dataclass(frozen=True)
class ScoringModel:
    version: str
    window_years: int
    long_haul_threshold_miles: int
    weights: dict[str, float]
    normalization: dict[str, float]


def load_scoring_model(path: str | Path | None = None) -> ScoringModel:
    """Load and validate the scoring configuration. Raises on invalid config."""
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)["scoring_model"]

    weights = dict(cfg["weights"])
    total = sum(weights.values())
    if abs(total - 1.0) > 1e-6:
        raise ValueError(f"Scoring weights must sum to 1.0 (got {total:.6f})")
    if any(w <= 0 for w in weights.values()):
        raise ValueError("All scoring weights must be positive")

    return ScoringModel(
        version=str(cfg["version"]),
        window_years=int(cfg["analysis_window_years"]),
        long_haul_threshold_miles=int(cfg["long_haul_threshold_miles"]),
        weights=weights,
        normalization=dict(cfg["normalization"]),
    )


def normalize_component(key: str, raw: float, model: ScoringModel) -> float:
    """Map a raw observed value to a 0-100 sub-score. Deterministic."""
    n = model.normalization
    if key in ("demand_growth", "flight_growth"):
        # config cap is expressed in percent (15.0); raw values are fractions (0.15)
        cap = float(n["growth_pct_cap"]) / 100.0
        return _clip(100.0 * (raw / cap), 0.0, 100.0)
    if key == "load_factor":
        floor = float(n["load_factor_floor"])
        ceiling = float(n["load_factor_ceiling"])
        return _clip(100.0 * (raw - floor) / (ceiling - floor), 0.0, 100.0)
    if key == "utilization_trend":
        rng = float(n["utilization_trend_range_points"])
        return _clip(50.0 + 50.0 * (raw / rng), 0.0, 100.0)
    if key == "long_haul":
        cap = float(n["long_haul_share_cap"])
        return _clip(100.0 * (raw / cap), 0.0, 100.0)
    raise KeyError(f"Unknown scoring component: {key}")


def _clip(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def compute_score(
    raw_components: dict[str, float | None],
    model: ScoringModel,
) -> dict:
    """Compute the composite score with missing-component renormalization.

    Returns a fully decomposed result: per-component raw value, sub-score,
    weight used (renormalized if components are missing), and contribution.
    """
    available: dict[str, float] = {}
    missing: list[str] = []
    for key in COMPONENT_ORDER:
        raw = raw_components.get(key)
        if raw is None or (isinstance(raw, float) and math.isnan(raw)):
            missing.append(key)
        else:
            available[key] = float(raw)

    if not available:
        raise ValueError("No scoring components could be computed")

    total_weight = sum(model.weights[k] for k in available)
    renormalized = len(missing) > 0

    components = []
    score = 0.0
    for key in COMPONENT_ORDER:
        if key not in available:
            continue
        raw = available[key]
        sub = normalize_component(key, raw, model)
        w_used = model.weights[key] / total_weight
        contribution = w_used * sub
        score += contribution
        components.append({
            "key": key,
            "label": COMPONENT_LABELS[key],
            "raw_value": round(raw, 6),
            "sub_score": round(sub, 1),
            "configured_weight": model.weights[key],
            "weight_used": round(w_used, 4),
            "contribution": round(contribution, 2),
        })

    return {
        "score": round(score, 1),
        "components": components,
        "missing_components": missing,
        "weights_renormalized": renormalized,
        "model_version": model.version,
    }
