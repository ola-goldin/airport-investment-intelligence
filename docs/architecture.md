# Architecture

```
Dify  (Phase 1 chat orchestrator)
     ▼
┌──────────────────────────────────────────────────────────────┐
│ FastAPI analytics service (backend/app)                      │
│                                                              │
│  api/airports.py   — metrics / compare / rank / long-haul /  │
│                      utilization / scoring-model endpoints   │
│  api/chat.py       — deterministic fallback agent + memory   │
│  analytics/        — scoring.py, demand.py, utilization.py,  │
│                      metrics.py  (pure, testable functions)  │
│  data/             — bts.py, faa.py, metadata.py, loader.py  │
│  models/schemas.py — Pydantic responses                      │
│  runtime.py        — repo + scoring-model singletons         │
└──────────────┬───────────────────────────────────────────────┘
               ▼
┌──────────────────────────────────────────────────────────────┐
│ DuckDB table + Parquet cache (data/processed/t100.parquet)   │
│   traffic:   BTS T-100 schema (authoritative; seed fallback) │
│   metadata:  OurAirports schema (authoritative; seed fallback)│
└──────────────────────────────────────────────────────────────┘
```

## Data flow

1. On startup the repository loads traffic data (BTS T-100 download when
   `AIRPORT_AGENT_BTS_DOWNLOAD=1`, bundled calibrated seed otherwise) into a
   DuckDB table and writes a Parquet cache; airport metadata comes from
   OurAirports (same pattern).
2. Every analytics call goes through the repository (DuckDB SQL), producing
   observed KPIs per airport-year.
3. `scoring.py` normalizes KPIs against thresholds in `config/scoring.yaml`
   and computes the deterministic weighted score, with explicit
   missing-component renormalization.
4. Responses carry provenance (`data_source`, `assumptions`, scoping notes).
5. Dify (or the fallback `/api/chat`) orchestrates and explains; it cannot
   compute or alter numbers.

## Guardrails

- Weights validated to sum to 1.0 at load time; invalid config raises.
- Singletons (`runtime.py`) guarantee identical data across requests.
- All network access is opt-in and degrades to clearly labeled seeds.
- The KPI vocabulary avoids scientifically unobservable claims
  (`utilization_trend`, never "unmet demand" as a measured figure).

## Data-source endpoints (env-configurable)

The download endpoints for the three public sources live in
`backend/app/data/endpoints.py` and are overridable via environment variables
(no code change needed to point at a mirror or an updated endpoint):

| Source | Env variable | Default |
|---|---|---|
| BTS T-100 base URL | `BTS_BASE_URL` | `https://www.transtats.bts.gov/DownLoad_Table.asp` |
| BTS T-100 query template (`{year}` placeholder kept) | `BTS_T100_QUERY` | `?Table_ID=311&Year={year}&AllVars=1&Zype=csv` |
| FAA enplanements workbook | `FAA_ENPLANEMENTS_URL` | `https://www.faa.gov/airports/planning_capacity/passenger_allcargo_stats/passenger/media/cy23-all-enplanements.xlsx` |
| OurAirports full CSV | `OURAIRPORTS_URL` | `https://davidmegginson.github.io/ourairports-data/airports.csv` |

All four defaults are also duplicated in `.env.example` so test setups can
copy that file to `.env` as-is. The URLs only affect *which remote files*
are fetched when `AIRPORT_AGENT_BTS_DOWNLOAD=1`; the analytics schema and
the scoring model are unchanged by them. With the default `0`, no network
is touched and the git-committed seed datasets are used.

## Testing

- `tests/test_scoring.py` — weights, normalization boundaries, midpoint
  values, renormalization, invalid-config rejection.
- `tests/test_metrics.py` — CAGR, window logic, utilization delta,
  long-haul share math, region filtering, ranking order.
- `tests/test_api.py` — HTTP contracts via TestClient, including the five
  required chat question types and follow-up context handling.
- `tests/test_offline.py` — full-stack offline guarantee: network blocked,
  all key endpoints still serve from the git-committed seeds.

Run: `cd backend && python -m pytest tests -q`

## Phase roadmap

- **Phase 1 (done):** core analytics + API + fallback chat + Dify wiring.
- **Phase 2 (done):** React chat UI with Dify-iframe/fallback toggle
  (same deterministic backend in both modes; no scoring logic in the UI).
- **Phase 3 (done, optional bonus):** local Whisper STT microservice (`stt/`),
  isolated from the core; text input never depends on it.
- **Phase 4 (optional):** LangGraph governance / human-in-the-loop —
  intentionally skipped to protect the working core.
