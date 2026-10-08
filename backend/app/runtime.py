"""Process-wide runtime: repository + scoring model singletons.

The API and the fallback chat agent share these instances so every
response is reproducible from the same data and the same config.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.analytics.metrics import DATA_SOURCE_NOTES  # re-export convenience
from app.analytics.scoring import load_scoring_model
from app.data import bts as bts_mod
from app.data.faa import validation_summary
from app.data.loader import AirportDataRepository, get_repository
from app.data import poller as poller_mod


@lru_cache(maxsize=1)
def get_scoring_model() -> Any:
    return load_scoring_model()


def get_runtime() -> tuple[AirportDataRepository, Any]:
    return get_repository(), get_scoring_model()


def system_status() -> dict:
    repo, model = get_runtime()
    return {
        "status": "ok",
        "data_source": repo.data_source,
        "metadata_source": repo.meta_source,
        "data_source_note": DATA_SOURCE_NOTES.get(repo.data_source, repo.data_source),
        "data_source_chain": [
            "1. BTS T-100 download (only when AIRPORT_AGENT_BTS_DOWNLOAD=1)",
            "2. cached data/raw/bts/*.csv reused as DuckDB input",
            "3. bundled git seed dump data/raw/bts_t100_seed.csv",
        ],
        "endpoint_tried": bts_mod.t100_url(max(repo.years(), default=2023)) if repo.data_source == "bts_t100_download" else None,
        "endpoint_configured": bts_mod.BTS_SOURCE_LABEL,
        "years": repo.years(),
        "airports_tracked": len(repo.codes()),
        "scoring_model_version": model.version,
        "faa_validation": validation_summary(),
        "data_poller": poller_mod.poller_status(),
    }
