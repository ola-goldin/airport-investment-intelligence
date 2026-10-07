"""Live smoke test: boots uvicorn on a real port and exercises key endpoints."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import threading
import time

import httpx
import uvicorn

# The app package is mounted under the backend directory, which is added to
# sys.path above. Static analyzers still sometimes flag this dynamic import.
try:
    from app.main import app  # type: ignore[import-not-found]
except ModuleNotFoundError:
    backend_root = Path(__file__).resolve().parents[1] / "backend"
    if str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))
    from app.main import app  # type: ignore[import-not-found]

config = uvicorn.Config(app, host="127.0.0.1", port=8010, log_level="warning")
server = uvicorn.Server(config)
thread = threading.Thread(target=server.run, daemon=True)
thread.start()
for _ in range(50):
    if server.started:
        break
    time.sleep(0.2)

base = "http://127.0.0.1:8010"
c = httpx.Client(base_url=base, timeout=30.0)

print("--- health")
print(c.get("/api/health").json())
print("--- BOS score:", c.get("/api/airports/BOS/metrics").json()["scoring"]["score"])
print("--- New England rank top3:")
r = c.post("/api/airports/rank", json={"region": "New England"}).json()
for e in r["ranking"][:3]:
    print(f"  {e['airport']} {e['city']}, {e['state']} score={e['score']}")
print("--- ANC long haul:", c.get("/api/airports/ANC/long-haul").json()["long_haul_departures_share"])
print("--- chat: unmet SFO")
print(c.post("/api/chat", json={"message": "What is the unmet flight demand in SFO and why?"}).json()["answer"])
print("--- chat: compare LAX vs SNA")
print(c.post("/api/chat", json={"message": "Compare LA and Santa Ana congestion levels"}).json()["answer"][:400])
server.should_exit = True
thread.join(timeout=10)
print("SMOKE OK")
