"""Thin Firecrawl API client.

- `scrape()`  -> POST /scrape  (markdown/html/structured-extract formats)
- `search()`  -> POST /search  (keyword search across the web/site)
- Exponential-backoff retry (max 3 retries)
- Responses cached in Redis for FIRECRAWL_CACHE_TTL_SECONDS (default 30 min)
"""
import hashlib
import json
import logging
import time

import httpx

from ..config import settings
from ..services.cache import cache

logger = logging.getLogger(__name__)

MAX_RETRIES = 3


class FirecrawlError(Exception):
    pass


class FirecrawlNotConfigured(FirecrawlError):
    pass


class FirecrawlClient:
    def __init__(self):
        self.base_url = settings.firecrawl_base_url.rstrip("/")
        self.api_key = settings.firecrawl_api_key

    def _ensure_configured(self):
        if not self.api_key:
            raise FirecrawlNotConfigured(
                "FIRECRAWL_API_KEY is not set — configure it or enable DEMO_MODE"
            )

    def _cache_key(self, endpoint: str, payload: dict) -> str:
        digest = hashlib.sha256(
            json.dumps({"e": endpoint, "p": payload}, sort_keys=True).encode()
        ).hexdigest()
        return f"firecrawl:{digest}"

    def _post(self, endpoint: str, payload: dict) -> dict:
        self._ensure_configured()
        key = self._cache_key(endpoint, payload)
        cached = cache.get_json(key)
        if cached is not None:
            logger.debug("Firecrawl cache hit for %s", endpoint)
            return cached

        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = httpx.post(
                    f"{self.base_url}{endpoint}",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=90,
                )
                if resp.status_code == 429:
                    raise FirecrawlError("Rate limited by Firecrawl (429)")
                resp.raise_for_status()
                data = resp.json()
                if not data.get("success", True):
                    raise FirecrawlError(f"Firecrawl error: {data.get('error', 'unknown')}")
                cache.set_json(key, data, settings.firecrawl_cache_ttl_seconds)
                return data
            except (httpx.HTTPError, FirecrawlError) as exc:
                last_error = exc
                if attempt < MAX_RETRIES:
                    delay = 2 ** attempt  # 1s, 2s, 4s
                    logger.warning(
                        "Firecrawl %s attempt %d failed (%s) — retrying in %ss",
                        endpoint, attempt + 1, exc, delay,
                    )
                    time.sleep(delay)
        raise FirecrawlError(f"Firecrawl {endpoint} failed after retries: {last_error}")

    # --- public API -----------------------------------------------------------

    def scrape(self, url: str, *, formats: list | None = None,
               extract_schema: dict | None = None, extract_prompt: str | None = None,
               wait_for: int | None = None) -> dict:
        """Scrape a single URL. Returns the `data` object from Firecrawl."""
        payload: dict = {"url": url, "formats": formats or ["markdown"]}
        if extract_schema or extract_prompt:
            payload["formats"] = list({*(formats or []), "extract"})
            payload["extract"] = {}
            if extract_schema:
                payload["extract"]["schema"] = extract_schema
            if extract_prompt:
                payload["extract"]["prompt"] = extract_prompt
        if wait_for:
            payload["waitFor"] = wait_for
        data = self._post("/scrape", payload)
        return data.get("data", data)

    def search(self, query: str, *, limit: int = 10, site: str | None = None) -> list[dict]:
        """Web search restricted to a portal domain when `site` is given."""
        q = f"site:{site} {query}" if site else query
        data = self._post("/search", {"query": q, "limit": limit})
        return data.get("data", [])


firecrawl = FirecrawlClient()
