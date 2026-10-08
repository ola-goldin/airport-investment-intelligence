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
#    Docker Compose reads `.env` automatically, but Docker can never create
#    it — copy the template, or let scripts/setup_infra.ps1 do it for you.
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