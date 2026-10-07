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
deterministic chat (`POST /api/chat`) answers the same four question types
with live numbers; inside the Dify chatbot, failed tool calls make the
agent answer with its guardrail message ("I could not retrieve that from
the analytics API").

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
  provides a deterministic fallback agent (same four question types).

## 6. Files

- `openapi.yaml` — tool definition for Dify Cloud (tunnel URL)
- `openapi-local.yaml` — same tools with `host.docker.internal:8000`
  server URL, only relevant for a self-hosted Dify instance (not used in
  this deployment)
- `agent-prompt.md` — agent system prompt with the guardrails
  (no invented numbers, unmet-demand scoping, KPI vocabulary)