/**
 * Dify chatbot embed helpers — iframe embed variant.
 *
 * The embed snippet from Dify (app -> Publish -> Embed in site) is an iframe:
 *   <iframe src="https://udify.app/chatbot/<ID>" ... allow="microphone;..."></iframe>
 * The URL belongs to the hosted Dify Cloud workspace (see dify/README.md).
 *
 * Availability check: we cannot inspect the cross-origin iframe, so we probe
 * the chatbot URL with a no-cors fetch raced against a timeout. An empty URL
 * (Dify not configured yet), network errors or a slow response (Dify
 * unresponsive) resolve false and the app falls back to its own
 * deterministic chat (see App.jsx).
 */

export const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";
export const DIFY_CHATBOT_URL = import.meta.env.VITE_DIFY_CHATBOT_URL || "";
export const DIFY_TIMEOUT_MS = Number(import.meta.env.VITE_DIFY_TIMEOUT_MS || 8000);

/** Resolve true when the Dify chatbot URL responds, false on network error/timeout. */
export function checkDify() {
  if (!DIFY_CHATBOT_URL) return Promise.resolve(false);
  const timeout = new Promise((resolve) => setTimeout(() => resolve(false), DIFY_TIMEOUT_MS));
  const probe = fetch(DIFY_CHATBOT_URL, { mode: "no-cors", cache: "no-store" })
    .then(() => true)
    .catch(() => false);
  return Promise.race([probe, timeout]);
}
