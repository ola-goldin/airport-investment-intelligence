import { useCallback, useEffect, useState } from "react";
import "./styles.css";
import { API_BASE, DIFY_CHATBOT_URL, checkDify } from "./difyEmbed.js";
import FallbackChat from "./FallbackChat.jsx";

/**
 * Airport Investment Intelligence client.
 *
 * Primary chat  : Dify chatbot embed (see difyEmbed.js).
 * Fallback chat : built-in React chat calling the deterministic FastAPI
 *                 endpoint POST /api/chat — activated automatically when
 *                 Dify is unresponsive (embed error/timeout or no token).
 */

function StatusBanner({ mode, difyOk, apiOk, onRetry, onForceFallback, onForceDify }) {
  if (mode === "dify") {
    return (
      <div className="banner banner-ok">
        <strong>Dify (primary orchestrator)</strong> — embedded agent is live.
        <span className="banner-actions">
          <button className="link" onClick={onForceFallback}>Use fallback chat</button>
        </span>
      </div>
    );
  }
  const reason =
    difyOk === false
      ? "Dify embed is unreachable or not configured"
      : "Dify embed did not load in time";
  return (
    <div className="banner banner-fallback">
      <strong>Fallback chat (deterministic API)</strong> — {reason}.
      {apiOk === false && (
        <span className="banner-warn"> Backend at {API_BASE} is also unreachable.</span>
      )}
      <span className="banner-actions">
        <button className="link" onClick={onRetry}>Retry Dify</button>
        <button className="link" onClick={onForceDify}>Try Dify anyway</button>
      </span>
    </div>
  );
}

export default function App() {
  // mode: "checking" | "dify" | "fallback"
  const [mode, setMode] = useState("checking");
  const [difyOk, setDifyOk] = useState(null);
  const [apiOk, setApiOk] = useState(null);
  const [backend, setBackend] = useState(null);

  const checkBackend = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/health`);
      if (!res.ok) throw new Error();
      setBackend(await res.json());
      setApiOk(true);
    } catch {
      setApiOk(false);
    }
  }, []);

  const tryDify = useCallback(async () => {
    setMode("checking");
    const ok = await checkDify();
    setDifyOk(ok);
    setMode(ok ? "dify" : "fallback");
  }, []);

  useEffect(() => {
    checkBackend();
    tryDify();
  }, [checkBackend, tryDify]);

  return (
    <div className="app">
      <header className="header">
        <div>
          <h1>Airport Investment Intelligence Agent</h1>
          <p className="sub">
            Dify-orchestrated LLM over a deterministic FastAPI + DuckDB analytics layer.
          </p>
        </div>
        <div className="backend-status">
          {backend ? (
            <>
              <span className="dot dot-ok" /> API up · data: {backend.data_source || "unknown"}
              {backend.years?.length
                ? ` · ${backend.years[0]}–${backend.years[backend.years.length - 1]}`
                : ""}
            </>
          ) : (
            <>
              <span className="dot dot-bad" /> API unreachable ({API_BASE})
            </>
          )}
        </div>
      </header>

      <StatusBanner
        mode={mode}
        difyOk={difyOk}
        apiOk={apiOk}
        onRetry={tryDify}
        onForceFallback={() => setMode("fallback")}
        onForceDify={() => setMode("dify")}
      />

      {mode === "checking" && <div className="checking">Checking Dify availability…</div>}

      {mode === "fallback" && <FallbackChat apiOk={apiOk} setApiOk={setApiOk} />}

      {mode === "dify" && (
        <div className="dify-frame">
          <iframe
            src={DIFY_CHATBOT_URL}
            style={{ width: "100%", height: "100%", minHeight: 700 }}
            frameBorder="0"
            allow="microphone;clipboard-write"
            title="Dify Airport Investment Intelligence Agent"
          />
        </div>
      )}

      <footer className="footer">
        Scores are deterministic composites of observed KPIs (config/scoring.yaml) —
        not investment advice. The LLM never computes a number.
      </footer>
    </div>
  );
}
