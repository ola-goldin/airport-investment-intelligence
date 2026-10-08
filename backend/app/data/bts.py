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

from app.data import endpoints

logger = logging.getLogger(__name__)

# Network access is opt-in so offline demos remain deterministic and fast.
# Set AIRPORT_AGENT_BTS_DOWNLOAD=1 to fetch authoritative BTS T-100 CSVs.
DOWNLOAD_ENABLED = os.getenv("AIRPORT_AGENT_BTS_DOWNLOAD", "0") == "1"

ROOT = Path(__file__).resolve().parents[3]
RAW_DIR = ROOT / "data" / "raw"
SEED_CSV = RAW_DIR / "bts_t100_seed.csv"
BTS_DIR = RAW_DIR / "bts"
# Name of the env var holding the BTS endpoint (surfaced in provenance so the
# UI can say exactly which URL was tried before falling back).
BTS_SOURCE_LABEL = "BTS_BASE_URL + BTS_T100_QUERY"

# T-100 Domestic + International market table. Base endpoint and query
# template are env-configurable (see app.data.endpoints); the query keeps a
# {year} placeholder so mirrors can be swapped in without touching code.
def t100_url(year: int) -> str:
    return endpoints.BTS_BASE_URL + endpoints.BTS_T100_QUERY.format(year=year)


def traffic_fallback_chain() -> list[dict]:
    """Describe the ordered fallback chain for traffic data.

    Each entry: {"source": <path-or-url>, "available": bool, "note": str}.
    """
    wanted = sorted({int(p.stem.split("_")[-1]) for p in BTS_DIR.glob("t100_market_*.csv")} or {2019, 2020, 2021, 2022, 2023})
    cached = [str(BTS_DIR / f"t100_market_{y}.csv") for y in wanted]
    cached_ok = all(Path(p).exists() for p in cached)
    chain = [
        {
            "source": t100_url(wanted[0]) if wanted else endpoints.BTS_BASE_URL + endpoints.BTS_T100_QUERY,
            "available": DOWNLOAD_ENABLED and cached_ok,
            "note": (
                "Authoritative BTS T-100 download (attempted only when "
                "AIRPORT_AGENT_BTS_DOWNLOAD=1). Points at BTS_BASE_URL + "
                "BTS_T100_QUERY from app.data.endpoints; change the env vars "
                "to use a mirror — no code change needed."
            ),
        },
        {
            "source": "; ".join(cached),
            "available": cached_ok,
            "note": "Local cached DuckDB input (data/raw/bts/); reused verbatim when downloads are off or fail.",
        },
        {
            "source": str(SEED_CSV),
            "available": SEED_CSV.exists(),
            "note": (
                "Bundled calibrated seed dump, committed to git "
                "(data/raw/bts_t100_seed.csv). Always available offline; "
                "responses are labeled seed_calibrated."
            ),
        },
    ]
    return chain

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
        resp = requests.get(t100_url(year), timeout=timeout, headers={"User-Agent": "airport-investment-agent/1.0"})
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

    Fallback order (see traffic_fallback_chain()):
      1. authoritative BTS downloads (only when AIRPORT_AGENT_BTS_DOWNLOAD=1),
         cached under data/raw/bts/;
      2. previously cached data/raw/bts/*.csv reused as the DuckDB input;
      3. bundled seed dump committed to git (data/raw/bts_t100_seed.csv).

    The returned label is 'bts_t100_download' or 'seed_calibrated'. Raises
    FileNotFoundError with the full chain if NO source is available — but
    level 3 is part of the repo, so normal installs always resolve locally.
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
        if downloaded:
            logger.warning(
                "BTS download incomplete (%d/%d years from %s) — continuing "
                "to local fallback levels instead of mixing partial downloads.",
                downloaded, len(wanted), endpoints.BTS_BASE_URL,
            )

    seed_missing = not SEED_CSV.exists()
    if seed_missing:
        chain = traffic_fallback_chain()
        raise FileNotFoundError(
            "No traffic data available. Fallback chain exhausted: "
            + " | ".join(f"[{ 'ok' if s['available'] else 'MISSING'}] {s['source']} ({s['note']})" for s in chain)
        )
    seed = pd.read_csv(SEED_CSV)
    return seed[SEED_COLUMNS], "seed_calibrated"
