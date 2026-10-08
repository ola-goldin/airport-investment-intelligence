"""Offline guarantee: after `git clone` + `docker compose up`, the API serves
everything from the git-committed seed dataset — even if every external
endpoint (BTS TranStats, OurAirports, FAA, Cloudflare) is unreachable.

These tests force network access to fail and assert the data layer still
loads from the bundled seeds, and that the five documented endpoints answer.
"""
from __future__ import annotations

import fastapi.testclient as testclient
import pytest

import app.data.bts as bts_mod
import app.data.loader as loader_mod
import app.data.metadata as meta_mod
from app.main import app


def _blocked(*args, **kwargs):
    raise RuntimeError("network access disabled by offline test")


@pytest.fixture()
def offline_repo(monkeypatch):
    """Block all outbound HTTP and force the repository to rebuild from seed."""
    monkeypatch.setattr(bts_mod.requests, "get", _blocked)
    monkeypatch.setattr(meta_mod.requests, "get", _blocked)
    monkeypatch.setattr(bts_mod, "DOWNLOAD_ENABLED", False)  # git default
    monkeypatch.setattr(meta_mod, "DOWNLOAD_ENABLED", False)  # git default
    monkeypatch.setattr(loader_mod, "_repo", None)  # rebuild on next request
    yield
    loader_mod._repo = None  # leave a clean singleton for other tests


def test_seed_files_committed_to_repo():
    """The seeds are the offline contract — they must exist in the checkout."""
    assert bts_mod.SEED_CSV.exists(), "data/raw/bts_t100_seed.csv missing"
    assert meta_mod.SEED_CSV.exists(), "data/raw/ourairports/airports_seed.csv missing"


def test_endpoints_module_exposes_env_defaults(monkeypatch):
    """endpoints.py honors env overrides without code changes."""
    import importlib

    import app.data.endpoints as endpoints_mod

    monkeypatch.setenv("BTS_BASE_URL", "https://mirror.example/t100")
    monkeypatch.setenv("BTS_T100_QUERY", "?mirror=1&Year={year}")
    monkeypatch.setenv("FAA_ENPLANEMENTS_URL", "https://mirror.example/faa.xlsx")
    monkeypatch.setenv("OURAIRPORTS_URL", "https://mirror.example/airports.csv")
    endpoints_reloaded = importlib.reload(endpoints_mod)
    try:
        assert endpoints_reloaded.BTS_BASE_URL == "https://mirror.example/t100"
        assert endpoints_reloaded.BTS_T100_QUERY == "?mirror=1&Year={year}"
        assert endpoints_reloaded.FAA_ENPLANEMENTS_URL == "https://mirror.example/faa.xlsx"
        assert endpoints_reloaded.OURAIRPORTS_URL == "https://mirror.example/airports.csv"
    finally:
        importlib.reload(endpoints_mod)  # restore module-level defaults


def test_bts_url_composes_from_env(monkeypatch):
    """bts.t100_url() composes base + query with the year substituted."""
    import app.data.endpoints as endpoints_mod

    monkeypatch.setattr(endpoints_mod, "BTS_BASE_URL", "https://mirror.example/t100")
    monkeypatch.setattr(endpoints_mod, "BTS_T100_QUERY", "?mirror=1&Year={year}")
    assert (
        bts_mod.t100_url(2023)
        == "https://mirror.example/t100?mirror=1&Year=2023"
    )


def test_fallback_chain_seeds_last_and_available():
    """The chain always ends in the git-committed seed dump (offline-safe)."""
    chain = bts_mod.traffic_fallback_chain()
    assert len(chain) == 3
    assert chain[-1]["source"].endswith("bts_t100_seed.csv")
    assert chain[-1]["available"] is True


def test_missing_seed_raises_chain_error(monkeypatch, tmp_path):
    """If even the seed dump is missing, the error names every exhausted level."""
    monkeypatch.setattr(bts_mod, "SEED_CSV", tmp_path / "nope.csv")
    with pytest.raises(FileNotFoundError, match="Fallback chain exhausted"):
        bts_mod.load_traffic_data()


def test_all_endpoints_serve_seed_with_network_blocked(offline_repo):
    client = testclient.TestClient(app)

    health = client.get("/api/health")
    assert health.status_code == 200
    body = health.json()
    assert body["status"] == "ok"
    assert body["data_source"] == "seed_calibrated"
    assert body["metadata_source"] == "ourairports_seed"

    model = client.get("/api/airports/_scoring-model")
    assert model.status_code == 200
    assert abs(sum(model.json()["weights"].values()) - 1.0) < 1e-9

    rank = client.post("/api/airports/rank", json={"region": "New England"})
    assert rank.status_code == 200
    assert rank.json()["ranking"][0]["airport"] == "BOS"

    chat = client.post("/api/chat", json={"message": "How does the scoring work?"})
    assert chat.status_code == 200
    assert chat.json()["intent"] == "scoring_model"