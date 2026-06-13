#!/bin/sh
# NOTE: this file must keep LF line endings (enforced via .gitattributes and a
# sed pass in the Dockerfile) — a CRLF shebang breaks exec inside the container.
#
# Installs the free stealth browser (Chromium) into a MOUNTED VOLUME on first
# run, then runs the given command. Doing it at runtime (not baking it into the
# image) keeps the image slim and avoids the large-layer image-extract that can
# exhaust a small Docker Desktop disk. Failure is non-fatal — the app still
# starts (demo mode / any HTTP-only portals); JS-gated portals just stay empty.
set -e

BROWSERS_DIR="${PLAYWRIGHT_BROWSERS_PATH:-/root/.cache/ms-playwright}"

if [ "${INSTALL_BROWSER:-true}" = "true" ]; then
  if ls "$BROWSERS_DIR"/chromium-* >/dev/null 2>&1; then
    echo "[entrypoint] stealth browser already installed in $BROWSERS_DIR"
  else
    # Serialise installs across services (backend + scheduler share the volume).
    lock="$BROWSERS_DIR/.install.lock"
    mkdir -p "$BROWSERS_DIR"
    if mkdir "$lock" 2>/dev/null; then
      echo "[entrypoint] downloading stealth browser (one-time, into volume)…"
      python -m playwright install chromium \
        || echo "[entrypoint] WARNING: browser download failed — JS portals (GeM, NIC eProcurement) will be skipped. Check Docker disk space."
      rmdir "$lock" 2>/dev/null || true
    else
      echo "[entrypoint] another service is installing the browser — waiting…"
      i=0
      while [ -d "$lock" ] && [ "$i" -lt 150 ]; do sleep 2; i=$((i + 1)); done
    fi
  fi
fi

exec "$@"
