"""Process-wide runtime: repository + scoring model singletons.

The API and the fallback chat agent share these instances so every
response is reproducible from the same data and the same config.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.analytics.metrics import DATA_SOURCE_NOTES  # re-export convenience
from app.analytics.scoring import load_scoring_model
from app.data.faa import validation_summary
from app.data.loader import AirportDataRepository, get_repository


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
        "years": repo.years(),
        "airports_tracked": len(repo.codes()),
        "scoring_model_version": model.version,
        "faa_validation": validation_summary(),
    }
