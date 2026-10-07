"""FAA passenger boarding (enplanement) data — secondary validation source.

The FAA publishes annual enplanements as spreadsheet files. We attempt a
best-effort download for cross-validation; when unavailable we fall back to
the bundled seed and mark the source accordingly. FAA data is NOT used to
compute scores directly — it exists to sanity-check BTS-derived passenger
volumes.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

import pandas as pd
import requests

logger = logging.getLogger(__name__)

# Network access is opt-in (see bts.py note).
DOWNLOAD_ENABLED = os.getenv("AIRPORT_AGENT_BTS_DOWNLOAD", "0") == "1"

ROOT = Path(__file__).resolve().parents[3]
SEED_CSV = ROOT / "data" / "raw" / "bts_t100_seed.csv"

FAA_ENPLANEMENTS_URL = (
    "https://www.faa.gov/airports/planning_capacity/"
    "passenger_allcargo_stats/passenger/media/cy23-all-enplanements.xlsx"
)


def fetch_faa_enplanements(timeout: float = 20.0) -> pd.DataFrame | None:
    """Best-effort fetch of FAA CY enplanements. Returns None on failure."""
    if not DOWNLOAD_ENABLED:
        return None
    dest = ROOT / "data" / "raw" / "faa" / "cy-enplanements.xlsx"
    if dest.exists():
        try:
            return pd.read_excel(dest)
        except Exception:  # noqa: BLE001
            pass
    try:
        resp = requests.get(FAA_ENPLANEMENTS_URL, timeout=timeout, headers={"User-Agent": "airport-investment-agent/1.0"})
        resp.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(resp.content)
        return pd.read_excel(dest)
    except Exception as exc:  # noqa: BLE001
        logger.warning("FAA enplanements download failed: %s", exc)
        return None


def validation_summary() -> dict:
    """Report which validation source is available (never blocks scoring)."""
    faa = fetch_faa_enplanements()
    if faa is not None:
        return {"faa_enplanements_available": True, "note": "FAA CY enplanements fetched for validation."}
    return {
        "faa_enplanements_available": False,
        "note": "FAA data unavailable; using bundled calibrated seed for validation context.",
    }
