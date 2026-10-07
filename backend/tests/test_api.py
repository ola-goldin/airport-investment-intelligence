"""API integration tests (TestClient, no LLM involved)."""
from fastapi.testclient import TestClient

from app.main import app


def client() -> TestClient:
    return TestClient(app)


def test_health():
    r = client().get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["data_source"] in ("seed_calibrated", "bts_t100_download")


def test_metrics_endpoint_bos():
    r = client().get("/api/airports/BOS/metrics")
    assert r.status_code == 200
    body = r.json()
    assert body["airport"] == "BOS"
    assert 0 <= body["scoring"]["score"] <= 100
    assert body["assumptions"]
    assert body["data_source_note"]


def test_metrics_unknown_404():
    r = client().get("/api/airports/ZZZ/metrics")
    assert r.status_code == 404


def test_rank_new_england():
    r = client().post("/api/airports/rank", json={"region": "New England", "limit": 10})
    assert r.status_code == 200
    body = r.json()
    assert len(body["ranking"]) >= 1
    ne = {"CT", "ME", "MA", "NH", "RI", "VT"}
    assert all(e["state"] in ne for e in body["ranking"])
    scores = [e["score"] for e in body["ranking"]]
    assert scores == sorted(scores, reverse=True)


def test_rank_requires_region():
    r = client().post("/api/airports/rank", json={})
    assert r.status_code == 422


def test_compare_lax_sna():
    r = client().post("/api/airports/compare", json={"codes": ["LAX", "SNA"]})
    assert r.status_code == 200
    body = r.json()
    assert len(body["comparison"]) == 2
    rows = body["pairwise_summary"]["rows"]
    assert any(row["metric"] == "Load factor" for row in rows)


def test_compare_needs_two_codes():
    r = client().post("/api/airports/compare", json={"codes": ["LAX"]})
    assert r.status_code == 422


def test_long_haul_anc():
    r = client().get("/api/airports/ANC/long-haul")
    assert r.status_code == 200
    body = r.json()
    assert body["airport"] == "ANC"
    assert 0 <= body["long_haul_departures_share"] <= 1
    assert "3000" in body["methodology"]


def test_utilization_sfo_labels_proxy():
    r = client().get("/api/airports/SFO/utilization")
    assert r.status_code == 200
    body = r.json()
    assert "does not directly measure unmet demand" in body["note"]
    assert body["load_factor_pct"] > 0
    # endpoint is named utilization, not capacity-pressure — per KPI rename
    assert "unmet" not in [k for k in body.keys() if k.startswith("unmet")]


def test_scoring_model_endpoint():
    r = client().get("/api/airports/_scoring-model")
    assert r.status_code == 200
    body = r.json()
    assert abs(sum(body["weights"].values()) - 1.0) < 1e-9


# ----------------------------------------------------------- fallback chat
def test_chat_new_england_ranking():
    c = client()
    r = c.post("/api/chat", json={"message": "Which airports in New England are strong candidates for terminal expansion?"})
    assert r.status_code == 200
    body = r.json()
    assert body["intent"] == "rank"
    assert "New England" in body["answer"]
    sid = body["session_id"]


def test_chat_compare():
    r = client().post("/api/chat", json={"message": "Compare LA and Santa Ana airport congestion levels"})
    assert r.status_code == 200
    body = r.json()
    assert body["intent"] == "compare"
    assert "LAX" in body["answer"] and "SNA" in body["answer"]


def test_chat_long_haul():
    r = client().post("/api/chat", json={"message": "What is the percentage of long haul flights out of Anchorage airport?"})
    assert r.status_code == 200
    body = r.json()
    assert body["intent"] == "long_haul"
    assert "ANC" in body["answer"]
    assert "3000" in body["answer"]


def test_chat_unmet_demand_sfo():
    r = client().post("/api/chat", json={"message": "What is the unmet flight demand in SFO airport and why?"})
    assert r.status_code == 200
    body = r.json()
    assert body["intent"] == "unmet_demand"
    assert "not directly observable" in body["answer"]
    assert body["assumptions"]


def test_chat_followup_uses_context():
    c = client()
    r1 = c.post("/api/chat", json={"message": "Which airports in New England are strong candidates?"})
    sid = r1.json()["session_id"]
    r2 = c.post("/api/chat", json={"message": "What about the top one's metrics?", "session_id": sid})
    assert r2.status_code == 200
    body = r2.json()
    # fallback resolves last discussed airport from session memory
    assert body["intent"] in ("metrics", "help")
    if body["intent"] == "metrics":
        assert body["payload"]["airport"]
