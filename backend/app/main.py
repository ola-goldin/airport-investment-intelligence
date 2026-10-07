"""Airport Investment Intelligence Agent — FastAPI analytics service.

The LLM layer (Dify agent, or the fallback chat router) orchestrates and
explains. All numbers come from the deterministic analytics modules here.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.api import airports, chat
from app.runtime import system_status

app = FastAPI(
    title="Airport Investment Intelligence Agent",
    description=(
        "Deterministic airport KPI + scoring service. "
        "AI explains and orchestrates; deterministic code owns the methodology."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # demo scope; tighten for production
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(airports.router, prefix="/api")


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
