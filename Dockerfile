# PINEAL-HERETIC v2.0 — tek imajlı paket (multi-stage)
# 1. Aşama: frontend derlemesi (Svelte -> statik dist)
# 2. Aşama: Python runtime + FastAPI + Playwright/Chromium (scraper için)

# ---------- Stage 1: frontend ----------
FROM node:22-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---------- Stage 2: runtime ----------
FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PINEAL_PORT=8000

# Playwright/Chromium için sistem bağımlılıkları
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget gnupg ca-certificates fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt \
    && python -m playwright install --with-deps chromium

COPY backend/ ./backend/
COPY agent_core/ ./agent_core/
COPY config/ ./config/
COPY main.py scraper.py ./
COPY --from=frontend /app/frontend/dist ./frontend/dist

EXPOSE 8000
# PINEAL_TOKEN tanimliysa healthcheck X-API-Key header'i tasir;
# aksi halde 401 alip surekli unhealthy gorunurdu (B3).
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s \
  CMD python -c "import os,urllib.request;t=os.getenv('PINEAL_TOKEN');req=urllib.request.Request('http://127.0.0.1:8000/api/telemetry?client_id=hc',headers={'X-API-Key':t} if t else {});urllib.request.urlopen(req,timeout=4)" || exit 1

CMD ["sh", "-c", "uvicorn backend.api:app --host 0.0.0.0 --port ${PINEAL_PORT:-8000}"]
