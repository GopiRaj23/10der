FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# psycopg2-binary ships its own libpq; curl is used by the healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Stealth browser for JS portals (GeM/IREPS) is OPT-IN — it adds ~400 MB of
# Chromium to the image, which can exhaust a small Docker Desktop disk. The
# HTTP-scraped NIC/CPPP portals (the main real-data sources) work WITHOUT it.
# Enable when you want GeM and have disk headroom:
#     docker compose build --build-arg INSTALL_BROWSER=true
# (or set INSTALL_BROWSER=true in .env, which compose passes through).
ARG INSTALL_BROWSER=false
RUN if [ "$INSTALL_BROWSER" = "true" ]; then scrapling install; fi

COPY . .

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
