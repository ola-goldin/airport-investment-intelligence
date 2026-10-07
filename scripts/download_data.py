"""Public data ingestion script (optional; network required).

Downloads the authoritative public sources into the local cache so the
backend can serve live data instead of the bundled seed:

  - BTS T-100 (Domestic + International) market CSVs, 2019-2023
    -> data/raw/bts/t100_market_{year}.csv
  - OurAirports full metadata CSV
    -> data/raw/ourairports/airports.csv
  - FAA CY enplanements (validation only; never used in scoring)
    -> data/raw/faa/cy-enplanements.xlsx

Every download is best-effort; on failure the backend transparently falls
back to the bundled, clearly-labeled seed dataset (see scripts/seed_demo_data.py).
Run:  python scripts/download_data.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

# Enable downloads for the data-layer modules BEFORE importing them.
os.environ["AIRPORT_AGENT_BTS_DOWNLOAD"] = "1"

import importlib

# Import via importlib so the runtime can resolve the backend package even
# when the editor/linter does not treat the project root as a Python package.
bts = importlib.import_module("app.data.bts")
faa = importlib.import_module("app.data.faa")
metadata = importlib.import_module("app.data.metadata")

YEARS = [2019, 2020, 2021, 2022, 2023]


def main() -> None:
    print(f"repo root: {ROOT}")
    print("== BTS T-100 market CSVs ==")
    ok = 0
    for year in YEARS:
        path = bts.download_t100_year(year)
        status = f"ok -> {path}" if path else "FAILED (backend will use seed fallback)"
        print(f"  {year}: {status}")
        ok += 1 if path else 0
    if ok < len(YEARS):
        print(f"  note: {len(YEARS) - ok}/{len(YEARS)} years failed; "
              "the backend stays reproducible via the bundled seed.")

    print("== OurAirports metadata ==")
    df, source = metadata.load_metadata()
    print(f"  source: {source}; rows: {len(df)}")

    print("== FAA enplanements (validation only) ==")
    faa_df = faa.fetch_faa_enplanements()
    print(f"  available: {faa_df is not None}")

    print("Done. Restart the backend to pick up new data "
          "(data_source is reported in every API response).")


if __name__ == "__main__":
    main()