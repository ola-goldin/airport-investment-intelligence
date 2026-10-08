# Dify setup guide (chat orchestrator)

Dify is the primary chat interface per the implementation instructions. This
deployment uses **Dify Cloud only** (workspace at `udify.app`) — there is no
local Dify install and no local model server. The published
chatbot is embedded by the frontend (`frontend/.env` →
`VITE_DIFY_CHATBOT_URL=https://udify.app/chatbot/<TOKEN>`); if it is ever
unreachable, the frontend falls back to the deterministic chat
(`POST /api/chat`).

## Recommended free model (no cost, does not expire)

Configure once in the workspace (owner only) — **Integrations → Model
Provider**:

- **Groq (recommended)** — free Developer plan at https://console.groq.com
  (no credit card; API keys do not expire):
  1. Install the **GroqCloud** plugin (verified by Dify) and paste your key.
  2. Agent/LLM model: **`gpt-oss-120b`** — free plan allows 30 requests/min
     and 1000 requests/day; quotas reset daily, so demo traffic never hits a
     permanent limit.
  3. Speech-to-Text (bonus): **`whisper-large-v3-turbo`** (the plugin also
     ships `whisper-large-v3` and `distil-whisper-large-v3-en`) — also free
     on the same key (20 req/min, 2000 req/day). It is an **STT model, not an
     LLM**: it never appears in the agent's model dropdown — only under
     **Integrations → Model Provider → Default Models → Speech-to-Text**,
     and only after the GroqCloud plugin is installed, configured with your
     key, and updated to the latest marketplace version (0.0.19+). Then
     enable voice input on the app. Text chat works without STT.
- **Avoid Dify's built-in AI credits on the free Sandbox plan** — only 200
  message credits are included and they run out; every later message then
  fails until a provider key is added.
- Alternatives (free tiers with function calling, but no STT in Dify):
  Google AI Studio `gemini-2.5-flash`, or OpenRouter free (`:free`) models.

## 1. Start the analytics API

```powershell
cd <repo-root>\backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
# optional: serve live BTS data instead of the bundled seed
$env:AIRPORT_AGENT_BTS_DOWNLOAD = "1"; python -m uvicorn app.main:app --port 8000
```

Verify: http://localhost:8000/api/health

## 2. Expose the API to Dify (automatic)

Dify Cloud runs on Dify's servers, which cannot reach your `localhost`, so
the stack includes a **`tunnel` service** (cloudflared quick tunnel) that
`docker compose up` starts together with the backend:

1. Start everything: `docker compose up -d` (or `scripts\setup_infra.ps1`).
2. Read the ephemeral public URL: `docker compose logs tunnel` →
   `https://....trycloudflare.com` (also saved to `data/tunnel_url.txt`).
3. `scripts\setup_infra.ps1` **automatically syncs** this URL into
   `dify/openapi.yaml` (`servers[0].url`).
4. **When the tunnel restarts the URL changes** → re-sync the tool in Dify
   (*Integrations → Tools → Swagger API* → paste the updated
   `openapi.yaml`) and **republish** the app. `scripts\verify_infra.ps1`
   checks this sync for you.

Verify end-to-end: `python scripts/check_tunnel.py`. Alternative: deploy
the FastAPI service to a public host and point `servers[0].url` at it
(stable URL, no re-sync needed).

Without a reachable URL the demo still works: the frontend's built-in
deterministic chat (`POST /api/chat`) answers the same five question types
(incl. "How does the scoring work?") with live numbers; inside the Dify
agent answer with its guardrail message ("I could not retrieve that from
the analytics API").

### Tunnel died? (tool calls fail or return 500)

Quick-tunnel URLs are ephemeral — Cloudflare revokes them when idle while the
container keeps retrying a dead registration (`Unauthorized: Tunnel not
found` in `docker compose logs tunnel`, and the URL in
`data/tunnel_url.txt` no longer resolves). Dify tools then fail and the agent
replies "I could not retrieve that from the analytics API".

1. `docker compose restart tunnel`, then read the fresh URL:
   `docker compose logs tunnel` → `https://....trycloudflare.com`
2. Sync it into `data/tunnel_url.txt` and `dify/openapi.yaml` (`servers[0].url`).
3. Verify through the public URL: `python scripts/check_tunnel.py`
   (expect `TUNNEL CHECK OK`).
4. In Dify: *Integrations → Tools → Swagger API* → paste the updated
   `openapi.yaml`, save, **republish the app**, then re-ask the question.

The local backend is unaffected: `http://localhost:8000/api/health` keeps
answering from the git-committed seed dataset, and the web UI automatically
switches to the deterministic fallback chat.

## 3. Create the Agent app

1. In Dify Cloud (https://udify.app): sign up with Google/GitHub SSO — no
   API key needed just to create the workspace.
2. Select the free agent model configured above (e.g. Groq `gpt-oss-120b`).
3. Paste the contents of `agent-prompt.md` as the system prompt.

### Importing the tool (current Dify Cloud UI — as of late 2026)

Custom tools are managed at workspace level, NOT inside the app editor:

1. Left sidebar → **Integrations** → **Tools** → **Swagger API** tab.
2. Create from schema: **paste the full contents of `openapi.yaml`**
   (or import from a URL). Dify parses it and lists all 7 operations.
3. Authorization: **No auth** (our API has none).
4. Back inside the Agent app: **Add tool** → select the imported tools →
   **enable all 7** (getAirportMetrics, compareAirports, rankAirports,
   getLongHaulShare, getUtilization, getScoringModel, fallbackChat).

> **Trap:** importing the tool globally does NOT attach it to the agent.
> If the agent has no tool attached it will answer from memory and
> hallucinate plausible-looking tables (we observed exactly this: a
> fabricated 0-1-scale BOS ranking with wrong values). Always verify tool
> calls appear in the run's debug/log panel.

Reasoning-only models (e.g. deepseek-r1) are NOT suitable agent models —
pick a tool-calling chat model.

5. App → Publish → Embed in site → copy the `<iframe src>` URL
   (`https://udify.app/chatbot/<TOKEN>`) into `frontend/.env` as
   `VITE_DIFY_CHATBOT_URL`, then `docker compose restart frontend`.

> **Instructions disappearing after reopening the app:** prompt edits are
> only kept reliably once **published**. After pasting the system prompt
> into the Agent's Instructions field, click the **Publish / Save & Publish**
> button (top right of the orchestration page) before leaving. Also select
> the model **first** — with no model selected the agent settings panel may
> not save. If instructions are lost, re-paste from `agent-prompt.md`
> (kept in the repo as the source of truth) and publish again.

## 4. Test conversation set

| Question | Expected behavior |
|---|---|
| Which airports in New England are strong candidates for terminal expansion? | rankAirports; BOS typically tops the ranking |
| Compare LAX and SNA congestion levels | compareAirports; utilization framing |
| What percentage of long haul flights out of ANC? | getLongHaulShare; definition quoted |
| What is the unmet flight demand in SFO and why? | getUtilization + explicit "not directly observable" scoping |
| How does the scoring work? | getScoringModel; weights quoted |

### Verification log (late 2026)

- New England ranking via Dify tool call: **PASSED** — run debug panel shows
  a `rankAirports` node with request `{"region": "New England"}` and the
  correct deterministic response (BOS 82.2 > BDL 75.3 > PWM 75.0 >
  MHT 72.5 > PVD 72.3, 0-100 scale). Matches live-API values exactly.
- Prior hallucination (fabricated 0-1-scale ranking, no tool calls) was
  caused by the tool not being attached to the agent; resolved after
  importing via Integrations -> Tools -> Swagger API and attaching tools.
- Cosmetic: Dify's debug log may display the tool observation twice
  (parsed + raw). Verified the API itself returns single JSON — display
  artifact only.

## 5. Credentials note

- The published chatbot needs no credentials for visitors; anyone just
  opens http://localhost:5173.
- The workspace owner configures ONE free provider key (see "Recommended
  free model" above). No paid keys are required.
- If Dify is unavailable at any point, `POST /api/chat` on the local service
  provides a deterministic fallback agent (same five question types).

## 6. Files

- `openapi.yaml` — tool definition for Dify Cloud (tunnel URL)
- `openapi-local.yaml` — same tools with `host.docker.internal:8000`
  server URL, only relevant for a self-hosted Dify instance (not used in
  this deployment)
- `agent-prompt.md` — agent system prompt with the guardrails
  (no invented numbers, unmet-demand scoping, KPI vocabulary)
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
