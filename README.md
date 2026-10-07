# Airport Investment Intelligence Agent

AI-powered agent that identifies promising US airports for terminal
expansion/renovation investment. **AI explains and orchestrates; deterministic
code owns the methodology.**

## Architecture (2-layer, per plan)

1. **Deterministic analytics layer** (FastAPI + DuckDB + Parquet):
   all KPIs and scores are computed by testable code — the LLM never touches a
   number.
2. **AI orchestration layer (Dify Cloud)**: conversational agent that calls the
   analytics API, explains results, and surfaces assumptions. A deterministic
   fallback chat endpoint keeps the demo working without Dify.

## Quick start

```powershell
pip install -r requirements.txt

# regenerate the bundled seed datasets (already generated; deterministic)
python scripts\make_seed_data.py

# run the analytics API
cd backend
python -m uvicorn app.main:app --port 8000

# run the tests
python -m pytest tests -q
```

## One-command demo (Docker)

```bash
git clone <repo> && cd airport-investment-agent
docker compose up                 # backend :8000 + frontend :5173 + Dify tool tunnel
```

The `tunnel` service (cloudflared) starts with the stack and exposes the
backend to Dify Cloud — its servers cannot reach localhost, so tool calls
travel through the ephemeral `https://....trycloudflare.com` URL shown in
`docker compose logs tunnel`. `scripts\setup_infra.ps1` syncs that URL into
`dify/openapi.yaml` automatically.

`.env.example` documents every optional variable; the basic demo starts
without any of them (no API keys, no accounts). The `AIRPORT_AGENT_BTS_DOWNLOAD=1`
switch attempts authoritative public downloads and degrades to the bundled
seed automatically if the network is unavailable.

Endpoints: `GET /api/health`, `GET /api/airports/{code}/metrics`,
`POST /api/airports/compare` `{"codes":["LAX","SNA"]}`,
`POST /api/airports/rank` `{"region":"New England"}`,
`GET /api/airports/{code}/long-haul`, `GET /api/airports/{code}/utilization`,
`GET /api/airports/_scoring-model`, `POST /api/chat`.

Dify wiring: see `dify/README.md` — the chat runs on the hosted Dify Cloud
workspace (`udify.app`); no local Dify install or model server is needed.

## Run script for automated setup

```powershell
# 1) Automated setup (idempotent; safe to re-run):
powershell -ExecutionPolicy Bypass -File scripts\setup_infra.ps1
#    - starts Docker Desktop if needed
#    - docker compose up: backend :8000 + frontend :5173 + public Dify tool
#      tunnel (+ voice STT :8100 unless -SkipVoice)
#    - waits for the tunnel to answer on its public URL, syncs
#      dify/openapi.yaml, runs verification, prints the service summary
#    options: -SkipVoice

# 2) Verify the environment at any time (read-only, exit code 0/1):
powershell -ExecutionPolicy Bypass -File scripts\verify_infra.ps1
powershell -ExecutionPolicy Bypass -File scripts\verify_infra.ps1 -RunTests
# 3) Optional: smoke-test the real Dify model (key: Dify -> App -> API Access):
powershell -ExecutionPolicy Bypass -File scripts\verify_infra.ps1 -DifyApiKey <key>
```

The verifier checks: backend API + deterministic ranking spot-check,
frontend, the **public Dify tool tunnel** (CORE), the optional voice STT,
the Dify embed URL configuration and reachability, and that
`dify/openapi.yaml` matches the live tunnel URL (BONUS). It ends with a
NOTICE listing the expected Dify model setup (Groq `gpt-oss-120b`, optional
`whisper-large-v3-turbo` speech-to-text) and reminding you to re-sync the
tool in Dify whenever the tunnel URL changes.

Everything runs without any API keys or accounts: the chat UI is the hosted
Dify Cloud chatbot (`https://udify.app/chatbot/...`, set by default in
`docker-compose.yml` and `frontend/.env`), and whenever it is unreachable
the frontend automatically runs its built-in deterministic fallback chat.
Rebuilding the Dify app itself
(model provider, Agent app, tool import) happens once in the browser — see
`dify/README.md`.

### macOS / Linux

`setup_infra.ps1` targets Windows PowerShell (it starts Docker Desktop via its
`.exe`). On macOS/Linux, run the equivalent steps manually:

```bash
# 1) Install Docker (Desktop or Engine), then start the demo stack
#    (backend :8000 + frontend :5173 + optional STT :8100):
docker compose --profile voice up -d --build

# 2) Verify (optional, needs PowerShell Core: brew install powershell / snap):
pwsh -File scripts/verify_infra.ps1
```

The `tunnel` service starts with the stack; read its URL with
`docker compose logs tunnel` and re-sync the tool in Dify whenever it
changes (on Windows, `setup_infra.ps1` does this sync automatically).

Hardware guidance: Docker Desktop with ≥ 4 GB RAM free. Ports used: 8000
(backend), 5173 (frontend), 8100 (STT).

## Data sources (per user directives)

- **BTS T-100 (authoritative traffic source).** The code attempts to download
  and cache official BTS T-100 market CSVs (`bts.py`) when
  `AIRPORT_AGENT_BTS_DOWNLOAD=1`. Without network access, a bundled, clearly
  labeled **real-world-calibrated seed** (`seed_calibrated`) is used and
  flagged in every API response — the demo never silently pretends to use live
  data.
- **OurAirports (authoritative metadata/reference source).** Names, cities,
  states, coordinates come from the public OurAirports dataset (`metadata.py`);
  bundled seed fallback when offline.
- **FAA enplanements (secondary validation only)** — fetched when network
  access is enabled; never used in scoring.

## Scoring methodology

Expansion Opportunity Score = weighted composite of **observed** KPIs
(config in `config/scoring.yaml`; weights validated at load time):

| Component | Weight | Definition (observed) |
|---|---|---|
| `demand_growth` | 0.30 | Passenger CAGR over trailing 3-year window |
| `load_factor` | 0.25 | Passengers / available seats, latest year |
| `utilization_trend` | 0.20 | Year-over-year change in load factor (points) |
| `flight_growth` | 0.15 | Scheduled-departure CAGR, same window |
| `long_haul` | 0.10 | Share of departing nonstop segments ≥ 3000 mi |

Missing components cause **explicit weight renormalization**, reported in the
response (`weights_renormalized`, `missing_components`) — never silent.

### KPI renaming rationale (user directive)

Earlier drafts used "capacity pressure"/"unmet demand" proxies. Public aviation
data cannot observe unmet demand (travellers who cannot obtain a seat are never
counted), so those names implied unscientific precision. The KPIs were renamed
to describe exactly what they measure (`utilization_trend` = observed Δ load
factor), and every unmet-demand answer explicitly states it is **not directly
observable**, presenting observed utilization indicators instead.

## AI usage disclosure

- Code (Python/FastAPI/DuckDB/tests/docs) was authored with AI assistance
  (Cline) under the approved phased plan.
- All numerical methodology is deterministic code; the LLM's role is
  orchestration and explanation only, enforced by the system prompt
  (`dify/agent-prompt.md`) and tool design (LLM has no write access to
  analytics or scoring).

## Example questions (all four exam questions verified)

| Question | Route | Notes |
|---|---|---|
| Which airports in New England are strong candidates for terminal expansion? | `rankAirports` | Identifies New England airports, ranks by deterministic score, surfaces components |
| Compare LA and Santa Ana airport congestion levels | `compareAirports` | LA→LAX, Santa Ana→SNA; observed utilization framing + methodology |
| What percentage of long haul flights out of Anchorage airport? | `getLongHaulShare` / `calculate_long_haul_share` | Returns numerator, denominator, percentage, and the definition (≥ 3000 mi nonstop) |
| What is the unmet flight demand in SFO airport and why? | `getUtilization` / `calculate_capacity_pressure` | Explicit proxy statement — unmet demand is never reported as an observed figure |

Follow-ups keep conversational context ("What about SFO?" after a ranking) via
session state that never touches the calculations.

## Voice / local STT (optional bonus)

```text
Microphone -> local faster-whisper STT (stt/, port 8100) -> text -> Dify / agent
```

- 100% local; no OpenAI/Groq/Hugging Face credentials, no paid STT API.
- Isolated from the core backend; start explicitly with
  `docker compose --profile voice up` or `pip install -r stt/requirements.txt`.
- Model size/device are configurable (`STT_MODEL_SIZE`, `STT_DEVICE`); CPU with
  ~2 GB free RAM handles `tiny`/`base` in real time. See `stt/main.py`.
- If STT cannot start (hardware limits, missing package), **text input keeps
  working** — the main app returns HTTP 503 from the STT service and the
  frontend falls back to typed chat. Voice inside the Dify iframe additionally
  requires STT to be enabled in the Dify workspace.

## Reproducibility

- **Demo data:** bundled, deterministic, real-world-calibrated seed
  (`scripts/seed_demo_data.py` regenerates it) — flagged `seed_calibrated` in
  every response.
- **Live public data:** `scripts/download_data.py` fetches BTS T-100,
  OurAirports and FAA sources when `AIRPORT_AGENT_BTS_DOWNLOAD=1`
  (flagged `bts_t100_download`).
- **Same data + same `config/scoring.yaml` ⇒ same scores**, verified by
  `backend/tests` (`python -m pytest tests -q` from `backend/`).
- Optional LangGraph governance (scoring-change proposal → deterministic
  validation → human approval → versioned config) is intentionally **not**
  implemented — it is out of scope for the exam and must never compromise the
  working core.

## Known tradeoffs

- Seed fallback (documented in every response) trades live-data freshness for
  reproducibility; enabling one env var switches to authoritative BTS data.
- Long-haul detection uses nonstop stage length ≥ 3000 mi; connecting
  itineraries are out of scope (BTS T-100 reports segments).
- The analysis window (3y) currently spans the COVID recovery period, so
  growth rates are elevated across all airports; the *ranking* remains
  meaningful, absolute growth rates should be caveated (surfaced in
  `assumptions`).
- Region coverage is the full US; per-airport terminal-specific data (gate
  counts, terminal age) is out of scope for Phase 1.
