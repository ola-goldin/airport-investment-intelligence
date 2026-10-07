# Core backend (analytics API) — no secrets required.
FROM python:3.12-slim

WORKDIR /srv

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# IMPORTANT: preserve the repo's relative layout. The data/analytics modules
# resolve the repo root as three levels above their own file
# (<root>/backend/app/data/bts.py -> <root>). A flat copy (app -> /srv/app)
# makes ROOT resolve to "/" and breaks seed/config discovery.
COPY backend/app ./backend/app
COPY backend/pytest.ini ./backend/pytest.ini
COPY config ./config
COPY scripts ./scripts
COPY data/raw ./data/raw

# Intra-package imports use `from app...`, so put the package parent on the path.
ENV PYTHONPATH=/srv/backend

EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

