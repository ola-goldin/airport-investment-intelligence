"""Compare a pasted (suspected-hallucinated) ranking against the live API."""
import json
import urllib.request

BASE = open("data/tunnel_url.txt", encoding="utf-8").read().strip().rstrip("/")

def get(path):
    with urllib.request.urlopen(BASE + path, timeout=30) as r:
        return json.loads(r.read().decode())

def post(path, payload):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())

rank = post("/api/airports/rank", {"region": "New England", "limit": 10})
print("=== TRUE New England ranking (live API) ===")
for r in rank["ranking"]:
    print(f"{r['airport']:4s} score={r['score']:<6} pax_growth={r['passenger_growth_pct']}% "
          f"LF={r['load_factor']} util_trend={r['utilization_trend_points']}pts  {r['name']}")

print("\n=== Per-airport detail vs the pasted table ===")
for code, pasted_score in [("BOS", 74.1), ("MHT", 58.2), ("BDL", 56.9)]:
    m = get(f"/api/airports/{code}/metrics")
    sc = m["scoring"]
    comp = {c["key"]: (c["raw_value"], c["sub_score"]) for c in sc["components"]}
    print(f"{code}: TRUE score={sc['score']}  (pasted: {pasted_score})")
    for k in sorted(comp):
        raw, sub = comp[k]
        print(f"    {k:18s} raw={raw}  sub_score={round(sub,1)}")
