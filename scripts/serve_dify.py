"""Boot the analytics API + a public cloudflared quick-tunnel for Dify Cloud.

Dify Cloud agents cannot reach localhost, so the FastAPI service must be
exposed via a public URL. This script:
  1. starts uvicorn (app.main:app) on :8000 and waits for /api/health,
  2. starts `cloudflared tunnel --url http://localhost:8000` (quick tunnel,
     no Cloudflare account or credentials needed),
  3. parses the generated https://<something>.trycloudflare.com URL and writes
     it to data/tunnel_url.txt plus stdout.

Run:  python scripts/serve_dify.py
NOTE: Not needed with Docker — `docker compose up` starts the `tunnel`
service automatically and scripts/setup_infra.ps1 syncs the URL into
dify/openapi.yaml. Use this script only when running the backend with
plain uvicorn (no Docker).
Stop: Ctrl+C (shuts down both processes).
"""
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
URL_FILE = ROOT / "data" / "tunnel_url.txt"


def wait_for_health(timeout=60):
    import urllib.request

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen("http://localhost:8000/api/health", timeout=3) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(1)
    return False


def main():
    env = dict(os.environ)
    env.setdefault("PYTHONUNBUFFERED", "1")

    print("[1/3] starting uvicorn on :8000 ...", flush=True)
    api = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"],
        cwd=str(BACKEND),
        env=env,
    )
    if not wait_for_health():
        print("ERROR: API did not become healthy; aborting.", flush=True)
        api.terminate()
        sys.exit(1)
    print("      API healthy: http://localhost:8000/api/health", flush=True)

    print("[2/3] starting cloudflared quick tunnel ...", flush=True)
    cloudflared = shutil.which("cloudflared") or r"C:\Program Files (x86)\cloudflared\cloudflared.exe"
    tunnel = subprocess.Popen(
        [cloudflared, "tunnel", "--url", "http://localhost:8000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    public_url = None
    pattern = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
    deadline = time.time() + 60
    lines = []
    while time.time() < deadline:
        line = tunnel.stdout.readline() if tunnel.stdout else ""
        if line:
            lines.append(line.rstrip())
            m = pattern.search(line)
            if m:
                public_url = m.group(0)
                break
        elif tunnel.poll() is not None:
            break

    if not public_url:
        print("ERROR: could not obtain a tunnel URL. cloudflared output:", flush=True)
        for ln in lines[-20:]:
            print("  " + ln, flush=True)
        api.terminate()
        tunnel.terminate()
        sys.exit(1)

    URL_FILE.parent.mkdir(parents=True, exist_ok=True)
    URL_FILE.write_text(public_url, encoding="utf-8")

    print(f"[3/3] public URL: {public_url}", flush=True)
    print(f"      (written to {URL_FILE})", flush=True)
    print("      Use this as servers[0].url in dify/openapi.yaml before importing into Dify Cloud.", flush=True)
    print("      Press Ctrl+C to stop both processes.", flush=True)

    try:
        while True:
            if api.poll() is not None:
                print("API exited; shutting down tunnel.", flush=True)
                break
            if tunnel.poll() is not None:
                print("Tunnel exited; shutting down API.", flush=True)
                break
            time.sleep(2)
    except KeyboardInterrupt:
        pass
    finally:
        for proc in (tunnel, api):
            try:
                proc.terminate()
            except Exception:
                pass
        try:
            URL_FILE.unlink()
        except OSError:
            pass
        print("Stopped.", flush=True)


if __name__ == "__main__":
    main()
