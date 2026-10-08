import { useCallback, useEffect, useRef, useState } from "react";
import "./styles.css";
import { API_BASE, DIFY_CHATBOT_URL, checkDify } from "./difyEmbed.js";
import FallbackChat from "./FallbackChat.jsx";

// How often the UI re-checks the backend health / poller status. Kept short so
// a background data refresh is reflected in the UI promptly without hammering it.
const HEALTH_POLL_MS = 5000;

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
      <strong>Fallback chat (deterministic API)</strong> — {reason}.{" "}
      Serving local git-seeded data from the FastAPI + DuckDB layer.
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
  // Timestamp of the most recent background data refresh, plus a transient
  // flag used to flash the "data updated" badge when the poller completes a cycle.
  const [dataUpdatedAt, setDataUpdatedAt] = useState(null);
  const [justUpdated, setJustUpdated] = useState(false);
  const lastCyclesRef = useRef(null);

  const formatTime = (iso) => {
    try {
      return new Date(iso).toLocaleTimeString();
    } catch {
      return iso;
    }
  };

  const checkBackend = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/health`);
      if (!res.ok) throw new Error();
      const data = await res.json();
      setBackend(data);
      setApiOk(true);
      // Detect a background refresh: the poller increments its cycle count on
      // every completed refresh, so a rise means fresh data was swapped in.
      const cycles = data?.data_poller?.cycles ?? 0;
      if (lastCyclesRef.current !== null && cycles > lastCyclesRef.current) {
        setDataUpdatedAt(data?.data_poller?.last_refresh_at || new Date().toISOString());
        setJustUpdated(true);
      }
      lastCyclesRef.current = cycles;
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

  // Poll backend health / poller status on an interval (and once immediately) so
  // background data refreshes are reflected live; Dify is checked only once.
  useEffect(() => {
    checkBackend();
    const id = setInterval(checkBackend, HEALTH_POLL_MS);
    return () => clearInterval(id);
  }, [checkBackend]);

  useEffect(() => {
    tryDify();
  }, [tryDify]);

  // Clear the transient "just updated" highlight a few seconds after it fires.
  useEffect(() => {
    if (!justUpdated) return;
    const id = setTimeout(() => setJustUpdated(false), 4000);
    return () => clearTimeout(id);
  }, [justUpdated]);

  return (
    <div className="app">
      <header className="header">
        <div>
          <h1>Airport Investment Intelligence Agent</h1>
          <p className="sub">
            Dify-orchestrated LLM over a deterministic FastAPI + DuckDB analytics
            layer — offline-ready from a bundled seed dump, and polls for updated
            source data when available.
          </p>
        </div>
        <div className="backend-status">
          {backend ? (
            <>
              <span className="dot dot-ok" /> API up · data: {backend.data_source || "unknown"}
              {backend.years?.length
                ? ` · ${backend.years[0]}–${backend.years[backend.years.length - 1]}`
                : ""}
              {backend.endpoint_tried && (
                <span title={`Fetched from ${backend.endpoint_tried}`}>
                  {" "}· src: {backend.endpoint_tried}
                </span>
              )}
              {!backend.endpoint_tried && (
                <span title="Offline seed dump committed to git; swap sources via env (see .env.example) without code changes">
                  {" "}· seed: local git dump
                </span>
              )}
              {backend.data_poller?.enabled && backend.data_poller?.running && (
                <span
                  className="poll-live"
                  title={`Background poller refreshes the data cache every ${backend.data_poller.interval_seconds}s`}
                >
                  <span className="poll-dot" /> live · {backend.data_poller.interval_seconds}s
                  {backend.data_poller.cycles > 0 ? ` · ${backend.data_poller.cycles}×` : ""}
                </span>
              )}
            </>
          ) : (
            <>
              <span className="dot dot-bad" /> API unreachable ({API_BASE})
            </>
          )}
        </div>
      </header>

      {dataUpdatedAt && (
        <div
          className={`data-updated${justUpdated ? " flash" : ""}`}
          role="status"
          aria-live="polite"
        >
          <span className="du-check">✓</span> Data refreshed · {formatTime(dataUpdatedAt)}
        </div>
      )}

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
            style={{ width: "100%", height: "100%" }}
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
