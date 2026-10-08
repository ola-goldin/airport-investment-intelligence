import { useCallback, useEffect, useRef, useState } from "react";
import { API_BASE, STT_BASE } from "./difyEmbed.js";

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
  // Voice: "idle" | "ready" | "recording" | "working" | "unavailable"
  // "ready": service reachable (checked once on mount); anything else is
  // decided per attempt so a stopped service never blocks typed chat.
  const [micState, setMicState] = useState("idle");
  const [micHint, setMicHint] = useState("");
  const recorderRef = useRef(null);
  const streamRef = useRef(null);
  const chunksRef = useRef([]);
  const sessionIdRef = useRef(crypto.randomUUID());
  const listRef = useRef(null);

  const stopTracks = useCallback(() => {
    try {
      (streamRef.current?.getTracks() || []).forEach((t) => t.stop());
    } catch {
      /* closing an already-closed stream is fine */
    }
    streamRef.current = null;
    recorderRef.current = null;
  }, []);

  // Confirm the service answers /health (any 2xx). Does NOT assert that a
  // Whisper model is loaded — that is decoded from /transcribe responses.
  const pingStt = useCallback(async (ms = 4000) => {
    try {
      const res = await fetch(`${STT_BASE}/health`, { cache: "no-store", signal: AbortSignal.timeout(ms) });
      return res.ok;
    } catch {
      return false;
    }
  }, []);

  useEffect(() => {
    pingStt().then((ok) => setMicState((s) => (s === "idle" && ok ? "ready" : s)));
    return stopTracks;
  }, [pingStt, stopTracks]);

  const toggleMic = useCallback(async () => {
    // Stop an active recording -> upload and transcribe.
    if (micState === "recording" && recorderRef.current) {
      try {
        recorderRef.current.stop();
      } catch {
        setMicState("ready");
        stopTracks();
      }
      return;
    }
    if (micState === "recording" || micState === "working") return;
    setMicHint("");
    // Browser prerequisites: recorder API + secure context for getUserMedia.
    const MR = window.MediaRecorder;
    if (!MR || !navigator.mediaDevices?.getUserMedia) {
      setMicState("unavailable");
      setMicHint("Voice needs a modern browser (Chrome/Edge/Firefox).");
      return;
    }
    if (!window.isSecureContext) {
      setMicState("unavailable");
      setMicHint("Voice needs a secure page (https or localhost).");
      return;
    }
    if (!(await pingStt())) {
      setMicState("unavailable");
      setMicHint(`Voice service is down (${STT_BASE}). Typed chat still works.`);
      return;
    }
    // Pick a container faster-whisper accepts: webm/opus (Chrome/Edge/Firefox),
    // mp4 (Safari 14.1+). wav fallback only if neither is supported.
    const candidates = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", ""];
    const mimeType = candidates.find((t) => !t || (MR.isTypeSupported && MR.isTypeSupported(t))) ?? "";
    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      setMicState("unavailable");
      setMicHint("Microphone blocked — allow access in the browser address bar.");
      return;
    }
    try {
      const rec = mimeType ? new MR(stream, { mimeType }) : new MR(stream);
      chunksRef.current = [];
      streamRef.current = stream;
      recorderRef.current = rec;
      rec.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) chunksRef.current.push(e.data);
      };
      rec.onstop = async () => {
        setMicState("working");
        setMicHint("Transcribing…");
        const blob = new Blob(chunksRef.current, { type: rec.mimeType || "audio/webm" });
        stopTracks();
        if (blob.size < 500) {
          setMicState("ready");
          setMicHint("Nothing recorded — hold the question, then tap Stop.");
          return;
        }
        try {
          const form = new FormData();
          form.append("audio", blob, "question.webm");
          const res = await fetch(`${STT_BASE}/transcribe`, {
            method: "POST",
            body: form,
            signal: AbortSignal.timeout(60000),
          });
          if (res.status === 503) {
            setMicHint("Voice model not loaded on the server. Typed chat still works.");
            return;
          }
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          const data = await res.json();
          const text = (data.text || "").trim();
          if (text) {
            setInput(text);
            setMicHint("Check the text, edit if needed, then Send.");
          } else {
            setMicHint("Heard nothing clear — try again, closer to the mic.");
          }
        } catch {
          setMicHint(`Could not reach the voice service (${STT_BASE}). Typed chat still works.`);
        } finally {
          setMicState((s) => (s === "working" ? "ready" : s));
        }
      };
      rec.onerror = () => {
        setMicState("ready");
        setMicHint("Recording failed — typed chat still works.");
        stopTracks();
      };
      rec.start();
      setMicState("recording");
      setMicHint("Recording… tap Stop when done.");
      // Hard stop at 60 s so a forgotten recording can't grow unbounded.
      setTimeout(() => {
        if (recorderRef.current?.state === "recording") recorderRef.current.stop();
      }, 60000);
    } catch {
      setMicState("ready");
      setMicHint("Could not start recording — typed chat still works.");
      stopTracks();
    }
  }, [micState, pingStt, stopTracks]);

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
        <button
          type="button"
          className={`mic${micState === "recording" ? " mic-live" : ""}`}
          onClick={toggleMic}
          disabled={sending || micState === "working"}
          title={
            micState === "recording"
              ? "Stop recording"
              : "Speak instead of typing (local voice service)"
          }
          aria-label={micState === "recording" ? "Stop recording" : "Start voice input"}
        >
          {micState === "recording" ? "⏹ Stop" : micState === "working" ? "…" : "🎙 Mic"}
        </button>
        <button type="submit" disabled={sending || !input.trim()}>Send</button>
      </form>
      {micHint && (
        <div className={`michint${micState === "unavailable" ? " michint-dim" : ""}`} role="status">
          {micHint}
        </div>
      )}
    </div>
  );
}
