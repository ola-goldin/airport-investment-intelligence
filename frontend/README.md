# Web client (React + Vite)

Browser client for the Airport Investment Intelligence Agent.

- **Primary chat**: the official **Dify chatbot embed** (bubble script) so the
  LLM-orchestrated agent with tool calls is used.
- **Fallback chat**: a built-in React chat that calls the deterministic
  FastAPI endpoint `POST /api/chat` directly. It activates automatically when
  the Dify embed script fails to load or exceeds the timeout — the same
  resilience path as `dify/README.md` §5.

## 1. Start the backend

```powershell
cd <repo-root>\backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 2. Configure the client

```powershell
cd <repo-root>\frontend
Copy-Item .env.example .env
# .env: set VITE_DIFY_CHATBOT_URL from the Dify Cloud workspace
# (udify.app -> your Agent app -> Publish -> Embed in site, the
# <iframe src="..."> URL, e.g. https://udify.app/chatbot/<TOKEN>).
# Leave it empty to use the built-in fallback chat.
```

On load the app probes the chatbot URL (`no-cors` fetch, 8 s timeout). If Dify
responds, the chatbot is rendered inline as an iframe (with
`allow="microphone;clipboard-write"` so voice input works). If the probe fails
or times out, the app switches to the built-in deterministic chat.

## 3. Run

```powershell
npm install
npm run dev
# open http://localhost:5173
```

Production build: `npm run build` (output in `dist/`), serve with any static
host (`npm run preview` to check).

## Behavior

| Situation | What the user sees |
|---|---|
| Dify chatbot URL responds within timeout | Inline Dify iframe (min-height 700px, mic-enabled) |
| Probe errors / times out | Built-in fallback chat, banner explains why, with **Retry Dify** |
| Dify up, backend down | Dify mode still works (it talks to its own API); fallback chat shows an error with the startup command |
| Backend down at start | Health dot red; fallback chat still attempts and reports failures per message |

The fallback chat renders the API's `answer`, an `intent` badge, and the
`assumptions` list — every number in a reply comes from the deterministic
analytics layer, never from an LLM.

## CORS

The backend allows all origins (`backend/app/main.py`), so the client can call
`http://localhost:8000` directly. Tighten `allow_origins` before any real
deployment.
