import { useCallback, useEffect, useRef, useState } from "react";
import { API_BASE } from "./difyEmbed.js";

const SUGGESTIONS = [
  "Which airports in New England are strong candidates for terminal expansion?",
  "Compare LAX and SNA congestion levels",
  "What percentage of long haul flights out of ANC?",
  "What is the unmet flight demand in SFO and why?",
  "How does the scoring work?",
];

/** Built-in deterministic chat (POST /api/chat) used when Dify is unresponsive. */
export default function FallbackChat({ apiOk, setApiOk }) {
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      text:
        "Deterministic fallback agent (Dify unavailable). Numbers come only " +
        "from the analytics API — I never invent them.",
    },
  ]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const sessionIdRef = useRef(crypto.randomUUID());
  const listRef = useRef(null);

  const send = useCallback(
    async (text) => {
      const message = text.trim();
      if (!message || sending) return;
      setInput("");
      setMessages((m) => [...m, { role: "user", text: message }]);
      setSending(true);
      try {
        const res = await fetch(`${API_BASE}/api/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message, session_id: sessionIdRef.current }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        setApiOk(true);
        setMessages((m) => [
          ...m,
          {
            role: "assistant",
            text: data.answer,
            intent: data.intent,
            assumptions: data.assumptions || [],
          },
        ]);
      } catch {
        setApiOk(false);
        setMessages((m) => [
          ...m,
          {
            role: "assistant",
            text:
              `Could not reach the analytics API at ${API_BASE}. ` +
              `Start it with: python -m uvicorn app.main:app --port 8000`,
          },
        ]);
      } finally {
        setSending(false);
      }
    },
    [sending, setApiOk]
  );

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight });
  }, [messages, sending]);

  return (
    <div className="chat">
      <div className="messages" ref={listRef}>
        {messages.map((m, i) => (
          <div key={i} className={`msg msg-${m.role}`}>
            <div className="bubble">
              <div className="text">{m.text}</div>
              {m.intent && <span className="intent">{m.intent}</span>}
              {m.assumptions?.length > 0 && (
                <details className="assumptions">
                  <summary>Assumptions ({m.assumptions.length})</summary>
                  <ul>
                    {m.assumptions.map((a, j) => (
                      <li key={j}>{a}</li>
                    ))}
                  </ul>
                </details>
              )}
            </div>
          </div>
        ))}
        {sending && (
          <div className="msg msg-assistant">
            <div className="bubble text muted">Retrieving from analytics API…</div>
          </div>
        )}
      </div>
      <div className="suggestions">
        {SUGGESTIONS.map((s) => (
          <button key={s} className="chip" disabled={sending} onClick={() => send(s)}>
            {s}
          </button>
        ))}
      </div>
      <form
        className="composer"
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={
            apiOk === false
              ? "Backend unreachable — retry in a moment"
              : "Ask about airport KPIs, rankings, comparisons…"
          }
          disabled={sending}
        />
        <button type="submit" disabled={sending || !input.trim()}>Send</button>
      </form>
    </div>
  );
}
