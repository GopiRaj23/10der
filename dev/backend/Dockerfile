FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# psycopg2-binary ships its own libpq; curl is used by the healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Indian government eProcurement portals (NIC GePNIC, GeM) refuse to serve their
# tender list without a JavaScript browser, so a stealth headless Chromium is
# required for real data. To avoid the large image layer that can exhaust a
# Docker Desktop disk, we split it:
#   - BUILD time: install only the system LIBRARIES Chromium needs (small, stable)
#   - RUNTIME (entrypoint): download the Chromium BINARY into a mounted volume
# Set INSTALL_BROWSER=false to skip both (demo mode / no real scraping).
ARG INSTALL_BROWSER=true
RUN if [ "$INSTALL_BROWSER" = "true" ]; then \
        python -m playwright install-deps chromium && rm -rf /var/lib/apt/lists/*; \
    fi

COPY . .
# Strip CRLF in case the build context was checked out on Windows — a CRLF
# shebang makes `exec` fail with "no such file or directory".
RUN sed -i 's/\r$//' docker-entrypoint.sh && chmod +x docker-entrypoint.sh

EXPOSE 8000

# Generous start-period: the first run may download the stealth browser into
# the volume (~1-2 min) before uvicorn starts listening.
HEALTHCHECK --interval=30s --timeout=5s --start-period=180s \
    CMD curl -fsS http://localhost:8000/health || exit 1

# Entrypoint downloads the browser into the volume on first run, then runs CMD.
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
