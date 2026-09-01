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
    PINEAL_ENV=production \
    PINEAL_PORT=8000

# Playwright/Chromium için sistem bağımlılıkları
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget gnupg ca-certificates fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --default-timeout=300 -r requirements.txt
RUN PLAYWRIGHT_DOWNLOAD_CONNECTION_TIMEOUT=300000     python -m playwright install --with-deps chromium ||     (echo "Retrying Playwright download..." && sleep 15 &&      PLAYWRIGHT_DOWNLOAD_CONNECTION_TIMEOUT=300000 python -m playwright install --with-deps chromium) ||     (echo "Retrying Playwright download 2..." && sleep 30 &&      PLAYWRIGHT_DOWNLOAD_CONNECTION_TIMEOUT=300000 python -m playwright install --with-deps chromium)

COPY backend/ ./backend/
COPY agent_core/ ./agent_core/
COPY config/ ./config/
COPY main.py scraper.py ./
COPY --from=frontend /app/frontend/dist ./frontend/dist

# Persistent data directories — production'da bunları kalıcı volume'a bağlayın.
# memory/: görev kanıt zinciri (kritik — kayıp geri alınamaz)
# cache/:  SQLite response cache (kaybedilebilir — yeniden doldurulur)
# ⚠ 2+ container aynı volume'u paylaşırsa tutarsızlık oluşur (process-local state).
RUN mkdir -p /app/memory /app/cache
VOLUME ["/app/memory", "/app/cache"]

EXPOSE 8000
# Production startup fails closed unless PINEAL_TOKEN is configured.
# Health: "ready" veya "degraded" → HTTP 200 (servis ayakta);
#         "failed" veya "starting" → HTTP 503 (container unhealthy sayılır).
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s \
  CMD python -c "\
import urllib.request, json, sys; \
r = urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4); \
d = json.loads(r.read()); \
sys.exit(0 if d.get('status') in ('ready', 'degraded') else 1)" || exit 1

CMD ["sh", "-c", "uvicorn backend.api:app --host 0.0.0.0 --port ${PINEAL_PORT:-8000}"]
