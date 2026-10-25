# Karyakarta backend. Build from the backend/ folder:  docker build -t karyakarta-api .
# Runs anywhere a container runs (Render, Railway, Fly, a VM). The database is Postgres (DATABASE_URL, Supabase) and uploaded files go to
# Supabase Storage (SUPABASE_URL + SUPABASE_SERVICE_KEY), so this container itself holds nothing that must survive a restart.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    KARYAKARTA_STORAGE=/tmp/storage \
    KARYAKARTA_DB=/tmp/karyakarta.db

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app
COPY seed ./seed
COPY scripts ./scripts
COPY demo_cache ./demo_cache

# Render sets $PORT; locally it falls back to 8765. Short graceful shutdown: browsers keep live-update (SSE) streams open.
EXPOSE 8765
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8765} --timeout-graceful-shutdown 5"]
