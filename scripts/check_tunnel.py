"""Verify the analytics API through the public tunnel URL (what Dify Cloud will use)."""
import json
import sys
import urllib.request

BASE = open("data/tunnel_url.txt", encoding="utf-8").read().strip().rstrip("/")

def get(path):
    with urllib.request.urlopen(BASE + path, timeout=30) as r:
        return json.loads(r.read().decode())

def post(path, payload):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())

health = get("/api/health")
print("health:", health.get("status"), "| data_source:", health.get("data_source"))

bos = get("/api/airports/BOS/metrics")
print("BOS score:", bos["scoring"]["score"], "| data_source:", bos["data_source"])

rank = post("/api/airports/rank", {"region": "New England"})
print("New England top:",
      [(r["airport"], r["score"]) for r in rank["ranking"][:3]])

lh = get("/api/airports/ANC/long-haul")
print("ANC long-haul departures share:", lh["long_haul_departures_share"])

print("TUNNEL CHECK OK" if health.get("status") == "ok" else "TUNNEL CHECK FAILED")
