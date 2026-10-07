# Optional local Whisper STT service (voice = bonus feature, never required).
FROM python:3.12-slim

WORKDIR /srv
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py ./

ENV STT_MODEL_SIZE=base
ENV STT_DEVICE=cpu

EXPOSE 8100
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8100"]
