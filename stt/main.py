"""Optional local speech-to-text microservice (bonus feature — never required).

Architecture (per plan §15):

    Microphone -> this local Whisper STT service -> text -> Dify / agent

- Fully local: faster-whisper runs on-device; NO cloud STT API, NO API keys.
- Isolated from the core analytics backend: the demo works with text input
  alone if this service is not running or cannot load a model.
- Starts with the stack by default (`docker compose up`); on Windows opt
  out with `setup_infra.ps1 -SkipVoice`. Bare-metal alternative:
    pip install -r stt/requirements.txt
    python -m uvicorn main:app --port 8100   (from inside stt/)

Hardware expectations (documented, not hidden):
  tiny  ~ 1 GB RAM, real-time on most CPUs
  base  ~ 1-2 GB RAM, real-time on modern 4+ core CPUs   (default)
  small ~ 2-3 GB RAM, slower on CPU; good on a modest GPU
  larger models need a GPU for acceptable latency
"""
from __future__ import annotations

import io
import logging
import os
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

try:  # guarded import: the service reports degraded status instead of crashing
    from faster_whisper import WhisperModel  # pyright: ignore[reportMissingImports]  # type: ignore[import-not-found]
    _IMPORT_ERROR: str | None = None
except Exception as _exc:  # noqa: BLE001 - report any import failure
    WhisperModel = None  # type: ignore[assignment]
    _IMPORT_ERROR = str(_exc)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("stt")

MODEL_SIZE = os.getenv("STT_MODEL_SIZE", "base")
DEVICE = os.getenv("STT_DEVICE", "cpu")
COMPUTE_TYPE = "int8" if DEVICE == "cpu" else "float16"

app = FastAPI(title="Airport Agent STT (local Whisper)", version="1.0.0")
# Same permissive CORS as the analytics backend: the browser (Vite dev on
# :5173 or any static host) calls :8100 cross-origin. Tighten for production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # demo scope; tighten for production
    allow_methods=["*"],
    allow_headers=["*"],
)
_model: Any | None = None


def get_model() -> Any | None:
    """Lazy singleton; returns None (never raises) if the model can't load."""
    global _model
    if WhisperModel is None:
        return None
    if _model is None:
        try:
            logger.info("loading faster-whisper model=%s device=%s", MODEL_SIZE, DEVICE)
            _model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)
        except Exception as exc:  # noqa: BLE001 - hardware limitations are expected
            logger.error("failed to load STT model: %s", exc)
            _model = None
    return _model


@app.get("/health")
def health() -> dict:
    return {
        "service": "stt",
        "engine": "faster-whisper (local)",
        "model": MODEL_SIZE,
        "device": DEVICE,
        "model_loaded": _model is not None,
        "import_ok": WhisperModel is not None,
        "import_error": _IMPORT_ERROR,
        "note": "Optional bonus service. The core demo never depends on STT.",
    }


@app.post("/transcribe")
async def transcribe(audio: UploadFile = File(...)) -> dict:
    """Transcribe an uploaded audio clip (webm/wav/mp3) to text."""
    model = get_model()
    if model is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Local STT unavailable (model failed to load or faster-whisper "
                "is not installed). Text input in the main app continues to work."
            ),
        )
    data = io.BytesIO(await audio.read())
    segments, info = model.transcribe(data, language=None)
    text = " ".join(s.text.strip() for s in segments).strip()
    return {"text": text, "language": info.language, "duration": round(info.duration, 2)}
