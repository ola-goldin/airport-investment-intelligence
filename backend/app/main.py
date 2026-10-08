"""Airport Investment Intelligence Agent — FastAPI analytics service.

The LLM layer (Dify agent, or the fallback chat router) orchestrates and
explains. All numbers come from the deterministic analytics modules here.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.api import airports, chat
from app.data import poller
from app.runtime import system_status

logger = logging.getLogger("app")

@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Start the background data poller; stop it on shutdown.

    Primitive polling is controlled by ``AIRPORT_AGENT_DATA_POLL_SECONDS``: the
    shipped ``.env`` enables it (60s); unset defaults to 0 (off), keeping the
    startup path deterministic and network-free unless polling is requested.
    """
    poller.start_poller()
    try:
        yield
    finally:
        poller.stop_poller()


app = FastAPI(
    title="Airport Investment Intelligence Agent",
    description=(
        "Deterministic airport KPI + scoring service. "
        "AI explains and orchestrates; deterministic code owns the methodology."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # demo scope; tighten for production
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(airports.router, prefix="/api")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Return a structured body instead of an opaque 500.

    The Dify agent surfaces `detail` verbatim to the user, so any unexpected
    failure must still be self-explanatory (and logged server-side).
    """
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "detail": (
                f"Internal analytics error ({type(exc).__name__}) while serving "
                f"{request.url.path}. The backend logs have the traceback; "
                "seed data itself is bundled in git."
            )
        },
    )


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


@app.post("/api/chat")
def chat_endpoint(req: ChatRequest):
    """Fallback conversational endpoint (deterministic intent routing).

    Primary chat/orchestration is Dify; this endpoint demonstrates
    resilience if Dify is unavailable (plan §14).
    """
    return chat.respond(req.message, req.session_id)


@app.get("/api/health")
def health():
    return system_status()


@app.get("/")
def root():
    return {
        "service": "Airport Investment Intelligence Agent",
        "docs": "/docs",
        "note": "All analytics are deterministic; scoring config is in config/scoring.yaml.",
    }
