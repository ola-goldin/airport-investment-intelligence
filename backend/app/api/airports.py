"""Deterministic analytics API endpoints.

These are the tools Dify (and the fallback chat agent) call. They return
structured JSON only — no LLM involvement in any number here.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.analytics import metrics as analytics
from app.models.schemas import (
    AirportMetricsResponse,
    CompareResponse,
    LongHaulResponse,
    RankResponse,
    UtilizationResponse,
)
from app.runtime import get_runtime, get_scoring_model, system_status

router = APIRouter(prefix="/airports", tags=["airports"])


@router.get("/{code}/metrics", response_model=AirportMetricsResponse)
def airport_metrics(code: str, end_year: int | None = Query(default=None, ge=2000, le=2100)):
    """Full observed metrics + deterministic score for one airport."""
    repo, model = get_runtime()
    result = analytics.get_airport_metrics(repo, model, code, end_year=end_year)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.post("/compare", response_model=CompareResponse)
def compare(payload: dict):
    """Compare two or more airports: {"codes": ["LAX", "SNA"]}."""
    codes = payload.get("codes")
    if not codes or not isinstance(codes, list) or len(codes) < 2:
        raise HTTPException(status_code=422, detail='Provide {"codes": [..]} with at least 2 codes.')
    repo, model = get_runtime()
    return analytics.compare_airports(repo, model, [str(c) for c in codes])


@router.post("/rank", response_model=RankResponse)
def rank(payload: dict):
    """Rank airports by region: {"region": "New England", "limit": 10}."""
    region = payload.get("region")
    if not region:
        raise HTTPException(status_code=422, detail='Provide {"region": "..."} (e.g. "New England").')
    try:
        limit = int(payload.get("limit", 10))
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail='"limit" must be an integer.')
    repo, model = get_runtime()
    result = analytics.rank_airports(repo, model, str(region), limit=limit)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/{code}/long-haul", response_model=LongHaulResponse)
def long_haul(code: str, year: int | None = Query(default=None, ge=2000, le=2100)):
    """Long-haul share of departing segments (observed, definition stated)."""
    repo, _ = get_runtime()
    target_year = year or repo.latest_year()
    result = analytics.long_haul_share(repo, code.upper(), target_year)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/{code}/utilization", response_model=UtilizationResponse)
def utilization(code: str):
    """Observed utilization indicators (load factor + trend).

    NOTE: this endpoint intentionally does NOT return an 'unmet demand'
    figure — public data cannot measure it. See the 'note' field.
    """
    repo, model = get_runtime()
    result = analytics.utilization_analysis(repo, model, code)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/_status/system")
def status():
    """System/data provenance status."""
    return system_status()


@router.get("/_scoring-model")
def scoring_model():
    """Expose the active deterministic scoring configuration."""
    model = get_scoring_model()
    return {
        "version": model.version,
        "analysis_window_years": model.window_years,
        "long_haul_threshold_miles": model.long_haul_threshold_miles,
        "weights": model.weights,
        "normalization": model.normalization,
        "note": "Weights are configuration-driven (config/scoring.yaml). The LLM cannot modify them.",
    }
