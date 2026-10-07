"""Pydantic response schemas (structured API responses per plan §20)."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ScoreComponent(BaseModel):
    key: str
    label: str
    raw_value: float
    sub_score: float
    configured_weight: float
    weight_used: float
    contribution: float


class ScoreBreakdown(BaseModel):
    score: float
    components: list[ScoreComponent]
    missing_components: list[str]
    weights_renormalized: bool
    model_version: str


class AirportMetricsResponse(BaseModel):
    airport: str
    profile: dict[str, Any]
    data_year: int
    metrics: dict[str, Any]
    scoring: ScoreBreakdown
    assumptions: list[str]
    data_source: str
    data_source_note: str


class RankEntry(BaseModel):
    airport: str
    name: str
    city: str
    state: str
    score: float
    passenger_growth_pct: float | None
    load_factor: float | None
    utilization_trend_points: float | None


class RankResponse(BaseModel):
    region: str
    scope: str
    ranking: list[RankEntry]
    assumptions: list[str]
    data_source: str


class CompareResponse(BaseModel):
    comparison: list[dict[str, Any]]
    pairwise_summary: dict[str, Any] | None
    data_source: str


class LongHaulResponse(BaseModel):
    airport: str
    year: int
    long_haul_departures_share: float | None
    long_haul_seat_share: float | None
    total_departures_performed: int
    long_haul_departures: int
    total_seats: int
    long_haul_seats: int
    methodology: str


class UtilizationResponse(BaseModel):
    airport: str
    year: int
    load_factor: float | None
    load_factor_pct: float | None
    passengers_per_departure: float | None
    utilization_trend_points: float | None
    prior_year: int | None
    prior_year_load_factor: float | None
    passengers: int | None
    demand_growth_pct: float | None
    note: str


class ChatResponse(BaseModel):
    session_id: str
    answer: str
    intent: str
    payload: dict[str, Any] = Field(default_factory=dict)
    assumptions: list[str] = Field(default_factory=list)
