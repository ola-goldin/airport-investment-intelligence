"""OurAirports metadata — the authoritative airport reference source.

Airport names, cities, states and coordinates come from the public
OurAirports dataset (http://ourairports.com), maintained by David Megginson.
We attempt to fetch and cache the full CSV; when offline we fall back to the
bundled seed metadata (data/raw/ourairports/airports_seed.csv).
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
RAW_DIR = ROOT / "data" / "raw" / "ourairports"
SEED_CSV = RAW_DIR / "airports_seed.csv"
FULL_CSV = RAW_DIR / "airports.csv"
OURAIRPORTS_URL = "https://davidmegginson.github.io/ourairports-data/airports.csv"

NEW_ENGLAND_STATES = {"CT", "ME", "MA", "NH", "RI", "VT"}
CALIFORNIA_STATES = {"CA"}

META_COLUMNS = ["iata_code", "name", "city", "state", "latitude_deg", "longitude_deg"]


def _try_fetch(timeout: float = 30.0) -> pd.DataFrame | None:
    if not DOWNLOAD_ENABLED:
        return None
    if FULL_CSV.exists():
        try:
            return pd.read_csv(FULL_CSV, usecols=["iata_code", "name", "municipality", "iso_region", "latitude_deg", "longitude_deg"])
        except Exception:  # noqa: BLE001
            pass
    try:
        resp = requests.get(OURAIRPORTS_URL, timeout=timeout, headers={"User-Agent": "airport-investment-agent/1.0"})
        resp.raise_for_status()
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        FULL_CSV.write_bytes(resp.content)
        return pd.read_csv(FULL_CSV, usecols=["iata_code", "name", "municipality", "iso_region", "latitude_deg", "longitude_deg"])
    except Exception as exc:  # noqa: BLE001
        logger.warning("OurAirports fetch failed: %s", exc)
        return None


def load_metadata(iata_codes: list[str] | None = None) -> tuple[pd.DataFrame, str]:
    """Return (metadata dataframe, source label).

    Full OurAirports download preferred; bundled seed otherwise.
    """
    full = _try_fetch()
    if full is not None:
        full = full[full["iata_code"].notna()].copy()
        full["state"] = full["iso_region"].str.replace("US-", "", regex=False)
        full = full.rename(columns={"municipality": "city"})
        out = full[META_COLUMNS]
        if iata_codes:
            out = out[out["iata_code"].isin(iata_codes)]
        if len(out) > 0:
            return out.reset_index(drop=True), "ourairports"
    return pd.read_csv(SEED_CSV)[META_COLUMNS], "ourairports_seed"


def region_to_states(region: str) -> set[str] | None:
    """Map a region name to state codes. None means 'all US states'."""
    r = region.strip().lower()
    if "new england" in r:
        return NEW_ENGLAND_STATES
    if "california" in r or "cali" in r:
        return CALIFORNIA_STATES
    if r in ("us", "united states", "usa", "all", "national", ""):
        return None
    # allow direct state names / codes
    upper = region.strip().upper()
    if upper in NEW_ENGLAND_STATES | CALIFORNIA_STATES | {"NY", "IL", "TX", "CO", "GA", "WA", "NV", "NC", "AZ", "FL", "NJ", "MN", "PA", "DC", "HI", "AK"}:
        return {upper}
    return None


REGION_ALIASES = {
    "New England": NEW_ENGLAND_STATES,
    "California": CALIFORNIA_STATES,
    "United States": None,
}
