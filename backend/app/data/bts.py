"""BTS T-100 traffic data — the authoritative source for traffic KPIs.

Primary path: download BTS T-100 (Domestic + International) market CSVs from
TranStats and cache them under data/raw/bts/. The TranStats endpoint is a
form-driven download and may be unavailable in constrained environments; in
that case we fall back to the bundled, clearly-labeled seed dataset
(data/raw/bts_t100_seed.csv) so the demo remains reproducible offline.

Every response exposes which source was used ("data_source").
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

import pandas as pd
import requests

logger = logging.getLogger(__name__)

# Network access is opt-in so offline demos remain deterministic and fast.
# Set AIRPORT_AGENT_BTS_DOWNLOAD=1 to fetch authoritative BTS T-100 CSVs.
DOWNLOAD_ENABLED = os.getenv("AIRPORT_AGENT_BTS_DOWNLOAD", "0") == "1"

ROOT = Path(__file__).resolve().parents[3]
RAW_DIR = ROOT / "data" / "raw"
SEED_CSV = RAW_DIR / "bts_t100_seed.csv"
BTS_DIR = RAW_DIR / "bts"

# T-100 Domestic + International market table (pre-filled download URL).
T100_URL = (
    "https://www.transtats.bts.gov/DownLoad_Table.asp"
    "?Table_ID=311&Year={year}&AllVars=1&Zype=csv"
)

SEED_COLUMNS = [
    "year",
    "airport_iata",
    "passengers",
    "seats",
    "departures_scheduled",
    "departures_performed",
    "long_haul_departures",
    "long_haul_seats",
]


def download_t100_year(year: int, timeout: float = 20.0) -> Path | None:
    """Best-effort download of a T-100 market CSV for one year. Returns None on failure."""
    dest = BTS_DIR / f"t100_market_{year}.csv"
    if dest.exists():
        return dest
    try:
        resp = requests.get(T100_URL.format(year=year), timeout=timeout, headers={"User-Agent": "airport-investment-agent/1.0"})
        resp.raise_for_status()
        BTS_DIR.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(resp.content)
        # sanity check: header must contain expected columns
        pd.read_csv(dest, nrows=2)
        return dest
    except Exception as exc:  # noqa: BLE001 - network is best-effort
        logger.warning("BTS T-100 download failed for %s: %s", year, exc)
        return None


def load_traffic_data(years: list[int] | None = None) -> tuple[pd.DataFrame, str]:
    """Return (traffic dataframe, data_source label).

    Attempts authoritative BTS downloads first, then falls back to the
    bundled seed CSV. The returned label is one of:
      'bts_t100_download' or 'seed_calibrated'.
    """
    frames: list[pd.DataFrame] = []
    downloaded = 0
    if DOWNLOAD_ENABLED:
        wanted = years or sorted({int(p.stem.split("_")[-1]) for p in BTS_DIR.glob("t100_market_*.csv")} or {2019, 2020, 2021, 2022, 2023})
        for year in wanted:
            path = download_t100_year(year)
            if path is not None:
                frames.append(pd.read_csv(path, low_memory=False))
                downloaded += 1
        if downloaded == len(wanted) and downloaded > 0:
            return pd.concat(frames, ignore_index=True), "bts_t100_download"

    seed = pd.read_csv(SEED_CSV)
    return seed[SEED_COLUMNS], "seed_calibrated"
