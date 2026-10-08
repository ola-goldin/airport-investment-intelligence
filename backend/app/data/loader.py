"""Data loader: raw traffic CSV -> DuckDB table + Parquet cache.

Builds a repository over:
  - traffic data (BTS T-100 authoritative schema; seed fallback)
  - airport metadata (OurAirports authoritative schema; seed fallback)

Analytics and API layers read exclusively through this repository so that
every numerical result is reproducible from the same underlying table.
"""
from __future__ import annotations

import threading
from pathlib import Path

import duckdb

from app.data import bts
from app.data import metadata as meta_mod

ROOT = Path(__file__).resolve().parents[3]
PROCESSED_DIR = ROOT / "data" / "processed"
PARQUET_PATH = PROCESSED_DIR / "t100.parquet"


class AirportDataRepository:
    """DuckDB-backed repository over traffic + airport metadata."""

    def __init__(self) -> None:
        self.con = duckdb.connect()
        traffic, self.data_source = bts.load_traffic_data()
        PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        self.con.register("traffic_df", traffic)
        self.con.execute("CREATE TABLE t100 AS SELECT * FROM traffic_df")
        # Parquet cache of the normalized table (per plan: Parquet storage layer)
        self.con.execute(f"COPY t100 TO '{PARQUET_PATH.as_posix()}' (FORMAT PARQUET)")

        meta_df, self.meta_source = meta_mod.load_metadata(
            iata_codes=[r[0] for r in self.con.execute("SELECT DISTINCT airport_iata FROM t100").fetchall()]
        )
        self.con.register("meta_df", meta_df)
        self.con.execute("CREATE TABLE airports_meta AS SELECT * FROM meta_df")

    # ------------------------------------------------------------------ basics
    def years(self) -> list[int]:
        rows = self.con.execute("SELECT DISTINCT year FROM t100 ORDER BY year").fetchall()
        return [r[0] for r in rows]

    def latest_year(self) -> int:
        row = self.con.execute("SELECT MAX(year) FROM t100").fetchone()
        if row is None or row[0] is None:
            raise RuntimeError("No traffic data loaded for t100")
        return int(row[0])

    def codes(self) -> list[str]:
        rows = self.con.execute("SELECT DISTINCT airport_iata FROM t100 ORDER BY airport_iata").fetchall()
        return [r[0] for r in rows]

    # ----------------------------------------------------------------- queries
    def totals(self, code: str, year: int) -> dict | None:
        row = self.con.execute(
            """
            SELECT passengers, seats, departures_scheduled, departures_performed,
                   long_haul_departures, long_haul_seats
            FROM t100 WHERE airport_iata = ? AND year = ?
            """,
            [code, year],
        ).fetchone()
        if row is None:
            return None
        keys = ["passengers", "seats", "departures_scheduled", "departures_performed",
                "long_haul_departures", "long_haul_seats"]
        return dict(zip(keys, row))

    def yearly_totals(self, code: str) -> dict[int, dict]:
        rows = self.con.execute(
            """
            SELECT year, passengers, seats, departures_scheduled, departures_performed,
                   long_haul_departures, long_haul_seats
            FROM t100 WHERE airport_iata = ? ORDER BY year
            """,
            [code],
        ).fetchall()
        keys = ["passengers", "seats", "departures_scheduled", "departures_performed",
                "long_haul_departures", "long_haul_seats"]
        return {r[0]: dict(zip(keys, r[1:])) for r in rows}

    def profile(self, code: str) -> dict | None:
        row = self.con.execute(
            "SELECT iata_code, name, city, state, latitude_deg, longitude_deg "
            "FROM airports_meta WHERE iata_code = ?",
            [code],
        ).fetchone()
        if row is None:
            return None
        keys = ["iata_code", "name", "city", "state", "latitude_deg", "longitude_deg"]
        return dict(zip(keys, row))

    def codes_in_states(self, states: set[str]) -> list[str]:
        rows = self.con.execute(
            "SELECT DISTINCT iata_code FROM airports_meta WHERE state IN ({})".format(
                ", ".join("?" for _ in states)
            ),
            sorted(states),
        ).fetchall()
        return [r[0] for r in rows]

    def close(self) -> None:
        self.con.close()


_repo_lock = threading.Lock()
_repo: AirportDataRepository | None = None


def get_repository() -> AirportDataRepository:
    """Process-wide singleton so all requests see identical data."""
    global _repo
    with _repo_lock:
        if _repo is None:
            _repo = AirportDataRepository()
        return _repo


def refresh_repository() -> AirportDataRepository:
    """Rebuild the repository from the data source and atomically swap it in.

    The new instance is built OFF the lock (the build can download + compile
    DuckDB), then swapped under ``_repo_lock`` so any concurrent request sees
    either the fully-built old repository or the fully-built new one — never a
    half-built table. The previous connection is intentionally not
    force-closed: an in-flight request may still be querying it, so it is left
    to the garbage collector (CPython closes the DuckDB connection on dealloc
    once the last reference drops). Used by the optional background poller
    (see ``app.data.poller``).
    """
    global _repo
    new_repo = AirportDataRepository()
    with _repo_lock:
        _repo = new_repo
    return new_repo
