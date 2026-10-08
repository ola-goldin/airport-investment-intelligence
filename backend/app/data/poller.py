"""Optional background poller that periodically refreshes the data cache.

Primitive polling: a daemon thread periodically calls the refresh below so the
API polls for updates without a restart. Controlled by
``AIRPORT_AGENT_DATA_POLL_SECONDS`` — the shipped ``.env`` enables it (60s); when
the variable is unset the code defaults to 0 (off), so the offline test suite
and unconfigured local runs stay deterministic and network-free.

When enabled, a daemon thread periodically calls
``app.data.loader.refresh_repository()`` — which re-runs the authoritative
data load path and atomically swaps the in-process repository — so the API can
serve fresher data without a restart. Intended to be used together with
``AIRPORT_AGENT_BTS_DOWNLOAD=1`` (see ``app.data.bts``); if downloads are
disabled the refresh simply re-materializes the bundled seed, which is a
harmless no-op data-wise.

Every refresh cycle is wrapped so a failure is recorded (and logged) rather
than raised: a bad poll can never crash the API. The poller's live status is
observable via ``GET /api/health`` -> ``data_poller``.
"""
from __future__ import annotations

import logging
import os
import threading
from datetime import datetime, timezone

from app.data import loader

logger = logging.getLogger(__name__)


def _poll_seconds() -> float:
    """Read the poll interval from the environment; 0 disables polling.

    A malformed value is treated as 0 (disabled) with a warning rather than
    crashing startup.
    """
    raw = os.getenv("AIRPORT_AGENT_DATA_POLL_SECONDS", "0")
    try:
        return max(float(raw), 0.0)
    except (TypeError, ValueError):
        logger.warning(
            "Invalid AIRPORT_AGENT_DATA_POLL_SECONDS=%r; polling disabled", raw
        )
        return 0.0


POLL_SECONDS = _poll_seconds()


class DataPoller:
    """Daemon thread that refreshes the data cache on a fixed interval."""

    def __init__(self, interval_seconds: float) -> None:
        self.interval_seconds = max(float(interval_seconds), 0.0)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.cycles = 0
        self.last_ok: bool | None = None
        self.last_error: str | None = None
        self.last_refresh_at: str | None = None

    @property
    def enabled(self) -> bool:
        return self.interval_seconds > 0

    def start(self) -> None:
        """Start the background thread. No-op when disabled or already running."""
        if not self.enabled or self._thread is not None:
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, name="data-poller", daemon=True
        )
        self._thread.start()
        logger.info(
            "Data poller started (interval=%ss)", self.interval_seconds
        )

    def stop(self, timeout: float = 5.0) -> None:
        """Signal the thread to stop and join it (best-effort, bounded wait)."""
        if self._thread is None:
            return
        self._stop.set()
        self._thread.join(timeout=timeout)
        self._thread = None

    def _run(self) -> None:
        # Wait first so startup is never delayed by an immediate refresh, then
        # refresh after every interval until asked to stop.
        while not self._stop.wait(self.interval_seconds):
            self.refresh_once()

    def refresh_once(self) -> bool:
        """Perform a single refresh cycle. Never raises; returns success."""
        now = datetime.now(timezone.utc).isoformat()
        try:
            repo = loader.refresh_repository()
        except Exception as exc:  # noqa: BLE001 - a failed poll must not crash the API
            self.cycles += 1
            self.last_ok = False
            self.last_error = f"{type(exc).__name__}: {exc}"
            self.last_refresh_at = now
            logger.warning("Data poller refresh failed: %s", exc)
            return False
        self.cycles += 1
        self.last_ok = True
        self.last_error = None
        self.last_refresh_at = now
        logger.info(
            "Data cache refreshed by poller (source=%s, airports=%d)",
            repo.data_source,
            len(repo.codes()),
        )
        return True

    def status(self) -> dict:
        return {
            "enabled": self.enabled,
            "interval_seconds": self.interval_seconds,
            "running": self._thread is not None,
            "cycles": self.cycles,
            "last_ok": self.last_ok,
            "last_error": self.last_error,
            "last_refresh_at": self.last_refresh_at,
        }


_poller: DataPoller | None = None


def get_poller() -> DataPoller | None:
    return _poller


def start_poller() -> DataPoller | None:
    """Create and start the process-wide poller if polling is enabled."""
    global _poller
    if POLL_SECONDS > 0 and _poller is None:
        _poller = DataPoller(POLL_SECONDS)
        _poller.start()
    return _poller


def stop_poller() -> None:
    global _poller
    if _poller is not None:
        _poller.stop()


def poller_status() -> dict:
    """Status dict for ``/api/health``; reports disabled when no poller exists."""
    if _poller is None:
        return {
            "enabled": False,
            "interval_seconds": POLL_SECONDS,
            "running": False,
            "cycles": 0,
            "last_ok": None,
            "last_error": None,
            "last_refresh_at": None,
        }
    return _poller.status()
