# Installation & Setup Guide

This guide covers the quickest ways to set up and run the Airport Investment Intelligence Agent.

---

## Prerequisites

- **Docker Desktop** (version 4.25+, recommended for full-stack run)
- **Python 3.13+** (if running locally without Docker)
- **Node.js 18+** (if running the frontend locally without Docker)

---

## Option 1: One-Command Stack (Docker — Recommended)

This starts the FastAPI backend (`:8000`), the React frontend (`:5173`), local Whisper speech-to-text (`:8100`), and the Cloudflare tunnel.

```bash
# 1. Clone the repository
git clone https://github.com/ola-goldin/airport-investment-intelligence.git
cd deloitte-airport-gent

# 2. Create your local environment file (test-ready defaults included)
#    Copy `.env.example` in order to create .env. For test purpoces ONLY the Dify chat url https://udify.app/agent/GCccKODnmASobyAm is disclosed there
#    or let scripts/setup_infra.ps1 do it for you.
Copy-Item .env.example .env   # PowerShell
# cp .env.example .env         # macOS/Linux

# 3. Launch all services
docker compose up
```

- **Web Console:** Open [http://localhost:5173](http://localhost:5173) in your browser.
- **Backend API Docs:** Open [http://localhost:8000/docs](http://localhost:8000/docs).

*(Windows shortcut: run `powershell -ExecutionPolicy Bypass -File scripts\setup_infra.ps1` to automatically handle Docker startup and tool URL syncing).*

---

## Option 2: Local Setup (Without Docker)

### 1. Backend Service

```bash
# Set up Python virtual environment
python -m venv venv

# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Generate the offline calibrated dataset
python scripts/make_seed_data.py

# Launch FastAPI backend
cd backend
python -m uvicorn app.main:app --port 8000
```

### 2. Frontend Service

Open a new terminal window:

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173).

---

## Option 3: Standalone CLI Agent (Zero Setup)

If you only need to run the analytical ranking without running web servers or Docker, execute the standalone Python script (uses standard library only):

```bash
# Run analysis and export results to JSON
python app.py

# Interactive terminal walkthrough
python demo.py
```

Results are saved to `airport_investment_results.json`.


## Configuration via Environment Variables

Every configurable value lives in `.env.example` (duplicated here for test
setups — copy it to `.env` as-is and everything works with stock settings).
Docker Compose reads `.env` automatically; `scripts/setup_infra.ps1` creates
it from `.env.example` on first run and never overwrites an existing one.

| Variable | Default | Purpose |
|---|---|---|
| `AIRPORT_AGENT_BTS_DOWNLOAD` | `0` | `1` attempts authoritative BTS/OurAirports/FAA downloads, else bundled seeds |
| `BTS_BASE_URL` | `https://www.transtats.bts.gov/DownLoad_Table.asp` | BTS T-100 download endpoint (see `backend/app/data/endpoints.py`) |
| `BTS_T100_QUERY` | `?Table_ID=311&Year={year}&AllVars=1&Zype=csv` | BTS query template; `{year}` placeholder is filled per download year |
| `FAA_ENPLANEMENTS_URL` | `…/passenger/media/cy23-all-enplanements.xlsx` | FAA validation workbook URL |
| `OURAIRPORTS_URL` | `…/ourairports-data/airports.csv` | OurAirports full CSV URL |
| `VITE_DIFY_CHATBOT_URL` | shared Dify chatbot | React iframe chat; empty → deterministic fallback chat |
| `VITE_API_BASE` | `http://localhost:8000` | Backend URL for the UI |
| `STT_MODEL_SIZE` / `STT_DEVICE` | `base` / `cpu` | Local Whisper model size and device |

No secrets exist in this repo: there is nothing to rotate, and no API keys
are hardcoded anywhere. Dify provider keys live in the Dify workspace UI,
never in git.

---

## Troubleshooting

- **Port in use (`8000`, `5173`, `8100`):** Stop the conflicting local process or update the port mapping in `docker-compose.yml`.
- **Windows Encoding Error:** If terminal characters look distorted, run `set PYTHONIOENCODING=utf-8` before running scripts.
- **Microphone access:** Speech-to-text requires accessing the app over `http://localhost` or `https` and allowing browser microphone permissions.

# Architecture & Technical Design Document

**Project:** Airport Investment Intelligence Agent  
**Purpose:** Assist investment analysts in identifying US airports where terminal expansion and renovation investments yield the highest return based on passenger and flight capacity growth.

---

## 1. System Architecture: Two-Layer Design

To eliminate numerical hallucinations and maintain strict auditability, the system enforces a hard separation between mathematical computation and conversational orchestration:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        AI Orchestration Layer                          │
│               (Dify Cloud / Fallback Chat Engine)                      │
│  • Parses user intent & resolves aviation entities (e.g., LA -> LAX)   │
│  • Calls backend endpoints via OpenAPI schema specifications           │
│  • Explains reasoning, highlights assumptions, and manages dialogue    │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ HTTP / OpenAPI Tool Calls
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                      Deterministic Analytics Layer                     │
│                       (FastAPI + DuckDB + Parquet)                     │
│  • Computes verified KPIs (CAGR, load factors, stage length ratios)    │
│  • Applies multi-criteria scoring algorithm                            │
│  • Enforces explicit weight renormalization for missing fields         │
│  • Zero LLM numerical calculations                                     │
└────────────────────────────────────────────────────────────────────────┘
```
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

### Layer Details

1. **Deterministic Analytics Layer (`FastAPI`, `DuckDB`, `Parquet`):**
   - Owns 100% of the numbers, formulas, and ranking logic.
   - All KPIs are calculated by unit-tested Python routines. The LLM never performs arithmetic or assigns raw scores.
   - Manages data ingestion from authoritative sources and bundled offline caches.

2. **AI Orchestration Layer (`Dify Cloud` with Fallback):**
   - The primary interface is hosted on Dify Cloud (`udify.app`), which interprets analyst questions, selects the appropriate tool, and formats qualitative explanations.
   - If Dify Cloud is unreachable or times out, the frontend automatically falls back to an internal deterministic chat endpoint (`POST /api/chat`) that routes queries directly to analytics routines without cloud dependencies.

3. **Voice Input (Bonus Feature):**
   - Dify chat uses cloud STT.
   - The fallback chat includes a mic button backed by a local `faster-whisper` container (`POST http://localhost:8100/transcribe`), offering zero-cloud, privacy-preserving voice transcription.

---

## 2. Scoring Methodology & KPI Definitions

The agent evaluates terminal expansion opportunities using a weighted composite score defined in `config/scoring.yaml`:

$$\text{Expansion Opportunity Score} = \sum_{i=1}^{n} (w_i \times \text{KPI}_i)$$

| Component | Weight | Definition & Analytical Rationale |
|---|---|---|
| `demand_growth` | **0.30** | Passenger Compound Annual Growth Rate (CAGR) over trailing 3-year window. Captures sustained growth in passenger demand. |
| `load_factor` | **0.25** | Total passenger enplanements / available seats (latest year). Measures aircraft capacity pressure and gate throughput density. |
| `utilization_trend` | **0.20** | Year-over-year change in load factor (percentage points). Highlights facilities experiencing accelerating flight congestion. |
| `flight_growth` | **0.15** | Scheduled aircraft departures CAGR over trailing 3-year window. Differentiates flight frequency growth from aircraft up-gauging. |
| `long_haul` | **0.10** | Nonstop departures $\ge 3{,}000$ miles / total departures. Identifies widebody aircraft requirements that demand higher-capital terminal gates. |

*(Standalone CLI scripts `app.py` and `demo.py` execute an equivalent baseline formula: $0.4 \times \text{Passenger Growth} + 0.3 \text{ Long-Haul Ratio} + 0.3 \times \text{Cargo Volume}$.)*

### Dynamic Weight Renormalization
If an airport is missing data for any metric, the system does not default missing values to zero (which would unfairly penalize the airport). Instead, it **renormalizes weights** dynamically across available components:

$$w_i' = \frac{w_i}{\sum_{k \in \text{available}} w_k}$$

The API response explicitly flags `weights_renormalized: true` and enumerates `missing_components` to maintain full transparency.

---

## 3. Assumptions, Uncertainty & Scoping

1. **Observability of "Unmet Demand":**
   - *Limitation:* Public aviation datasets (BTS T-100) record realized enplanements and actual seat capacity. Unserved passenger demand (travelers unable to book due to sold-out flights or lack of routes) is **not directly observable**.
   - *Scoping Rule:* The agent never invents an "unmet demand" number. Queries about unmet demand or congestion return observed proxy indicators (`utilization_trend`, load factors) accompanied by an explicit disclaimer stating that unserved demand is not directly measured in public data.
2. **Long-Haul Definition:**
   - Long-haul traffic is evaluated using nonstop segment stage length $\ge 3{,}000$ statute miles. Connecting itineraries are excluded because BTS T-100 reports airport-to-airport flight segments.
3. **Data Provenance:**
   - When network access is enabled (`AIRPORT_AGENT_BTS_DOWNLOAD=1`), the system downloads official BTS T-100 and OurAirports tables.
   - For offline evaluation, a bundled, real-world-calibrated seed (`seed_calibrated`) is used. Responses explicitly flag the data provenance tag (`seed_calibrated` vs. `bts_t100_download`).

---

## 4. Exam Question Coverage

| Exam Question | Primary Tool / Endpoint | Methodology Applied |
|---|---|---|
| *Which airports in New England are strong candidates for terminal expansion?* | `POST /api/airports/rank` | Filters by New England state codes, computes composite expansion scores, and breaks down KPI contributions. |
| *Compare LA and Santa Ana airport congestion levels.* | `POST /api/airports/compare` | Resolves names to `LAX` and `SNA`, comparing observed seat load factors and year-over-year utilization changes. |
| *What is the percentage of long haul flights out of Anchorage airport?* | `GET /api/airports/ANC/long-haul` | Computes ratio of nonstop departures $\ge 3{,}000$ miles over total departures. |
| *What is the unmet flight demand in SFO airport and why?* | `GET /api/airports/SFO/utilization` | Discloses the unobservability of unmet demand, then surfaces observed capacity pressure proxies. |

---

## 5. Where & How AI is Used

- **Natural Language Understanding & Entity Resolution:** The LLM maps conversational user queries (e.g., "LA", "Santa Ana", "New England") to standardized IATA codes (`LAX`, `SNA`) and regional filters.
- **Tool Orchestration:** The LLM inspects the available OpenAPI endpoints and decides which analytics calls to trigger based on user intent.
- **Contextual Synthesis & Explanations:** The LLM ingests the raw JSON returned by the analytics engine and crafts human-readable explanations, contextualizing the numbers without altering them.
- **Conversational Memory:** Preserves multi-turn state (e.g., answering "What about SFO?" after ranking New England airports) while routing subsequent questions back to the deterministic analytics engine.

---

## 6. Key Design Tradeoffs

1. **Deterministic Code vs. End-to-End LLM Generation:**
   - *Tradeoff:* Requires strict schema definitions and tool call wiring.
   - *Benefit:* Completely prevents mathematical hallucinations, guarantees reproducibility, and provides institutional investors with audit-grade data.
2. **Dual Chat Engine (Hosted Dify + Fallback React Chat):**
   - *Tradeoff:* Requires maintaining both OpenAPI definitions for Dify and a local fallback endpoint.
   - *Benefit:* Guarantees the system works during demos or offline environments even if cloud services are unavailable or API keys expire.
3. **Calibrated Offline Seed vs. Mandatory Live BTS Downloads:**
   - *Tradeoff:* Bundled seed data reflects snapshot data rather than real-time daily feeds.
   - *Benefit:* Guarantees instant, zero-failure local testing without depending on external government servers during an evaluation.
