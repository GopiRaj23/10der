"""Scrapling-based fetch engine — free and open-source, no API keys.

Replaces the previous Firecrawl integration. Three strategies, strongest-first
for anti-bot portals:

- ``http_page(url)``    curl_cffi HTTP with Chrome TLS fingerprint impersonation
                        (scrapling ``Fetcher``) — fast, no browser needed.
- ``stealth_page(url)`` patched headless Chromium with fingerprint spoofing
                        (scrapling ``StealthyFetcher``) — for JS-rendered /
                        bot-protected portals like GeM.
- ``dynamic_page(url)`` plain headless Chromium (scrapling ``DynamicFetcher``)
                        — fallback when the stealth profile misbehaves.

Browser strategies need a one-time ``scrapling install`` (downloads Chromium).
When the browser is missing they raise ``StealthUnavailable`` with that hint so
scrapers can degrade cleanly instead of crashing the worker.

Fetched HTML is cached in Redis for SCRAPE_CACHE_TTL_SECONDS (default 30 min)
so repeated runs / multi-keyword passes don't hammer the portals. robots.txt
checks and politeness delays happen in BaseScraper before calls reach here.
"""
from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from ..config import settings
from ..services.cache import cache

logger = logging.getLogger(__name__)

BROWSER_RETRIES = 2          # browser fetchers have no built-in retry
HTTP_RETRIES = 3             # passed straight to scrapling Fetcher
IMPERSONATE = "chrome"       # TLS/JA3 fingerprint presented by curl_cffi


class EngineError(Exception):
    """Recoverable fetch failure (network, HTTP status, render timeout)."""


class StealthUnavailable(EngineError):
    """Browser-based fetch requested but Chromium isn't installed —
    run `scrapling install` once to enable it."""


@dataclass
class Page:
    """Normalised fetch result. `select()` parses lazily with scrapling."""

    url: str
    status: int
    html: str

    def select(self):
        from scrapling.parser import Selector

        return Selector(self.html, url=self.url)


def _cache_key(strategy: str, url: str) -> str:
    return f"page:{strategy}:{hashlib.sha256(url.encode()).hexdigest()}"


def _cached(strategy: str, url: str) -> Page | None:
    data = cache.get_json(_cache_key(strategy, url))
    if data:
        logger.debug("page cache hit (%s) %s", strategy, url)
        return Page(url=url, status=data["status"], html=data["html"])
    return None


def _store(strategy: str, url: str, page: Page) -> None:
    cache.set_json(_cache_key(strategy, url),
                   {"status": page.status, "html": page.html},
                   settings.scrape_cache_ttl_seconds)


@lru_cache(maxsize=1)
def stealth_browser_ready() -> bool:
    """True when the Chromium that scrapling's browser fetchers launch is
    installed (i.e. `scrapling install` has been run). Cached per process."""
    for module in ("patchright.sync_api", "playwright.sync_api"):
        try:
            sync_playwright = __import__(module, fromlist=["sync_playwright"]).sync_playwright
            with sync_playwright() as p:
                if Path(p.chromium.executable_path).exists():
                    return True
        except Exception:
            continue
    return False


# --- strategies ----------------------------------------------------------------

def http_page(url: str, *, timeout: int = 30) -> Page:
    """HTTP fetch with Chrome impersonation. Retries with backoff internally."""
    if (page := _cached("http", url)) is not None:
        return page
    from scrapling.fetchers import Fetcher

    try:
        resp = Fetcher.get(
            url,
            impersonate=IMPERSONATE,
            stealthy_headers=True,
            timeout=timeout,
            retries=HTTP_RETRIES,
            follow_redirects=True,
            verify=False,  # several NIC portals ship broken cert chains
            proxy=settings.proxy_url or None,
        )
    except Exception as exc:
        raise EngineError(f"HTTP fetch failed for {url}: {exc}") from exc
    if resp.status >= 400:
        raise EngineError(f"HTTP {resp.status} for {url}")
    page = Page(url=url, status=resp.status, html=resp.html_content)
    _store("http", url, page)
    return page


def open_session(*, timeout: int = 30):
    """A cookie-persistent HTTP session (scrapling FetcherSession / curl_cffi)
    with our standard impersonation/retry/proxy settings. Use as a context
    manager; cookies (e.g. a GePNIC JSESSIONID) persist across .get() calls,
    which lets scrapers follow a portal's real navigation flow — home page →
    session-tokenised list link — entirely over HTTP, no browser.
    """
    from scrapling.fetchers import FetcherSession

    return FetcherSession(
        impersonate=IMPERSONATE, stealthy_headers=True, timeout=timeout,
        retries=HTTP_RETRIES, follow_redirects=True, verify=False,
        proxy=settings.proxy_url or None,
    )


def _browser_fetch(fetcher_name: str, url: str, *, wait_selector: str | None,
                   timeout_ms: int, network_idle: bool) -> Page:
    if (page := _cached(fetcher_name, url)) is not None:
        return page
    if not stealth_browser_ready():
        raise StealthUnavailable(
            "Headless Chromium not installed — run `scrapling install` once "
            "(free) to enable JS-rendered portals like GeM"
        )
    from scrapling import fetchers

    fetcher = getattr(fetchers, fetcher_name)
    kwargs: dict = {"headless": True, "timeout": timeout_ms,
                    "network_idle": network_idle}
    if wait_selector:
        kwargs["wait_selector"] = wait_selector
    if settings.proxy_url:
        kwargs["proxy"] = settings.proxy_url

    last_error: Exception | None = None
    for attempt in range(BROWSER_RETRIES + 1):
        try:
            resp = fetcher.fetch(url, **kwargs)
            if resp.status >= 400:
                raise EngineError(f"HTTP {resp.status} for {url}")
            page = Page(url=url, status=resp.status, html=resp.html_content)
            _store(fetcher_name, url, page)
            return page
        except StealthUnavailable:
            raise
        except Exception as exc:
            last_error = exc
            if attempt < BROWSER_RETRIES:
                delay = 2 ** attempt
                logger.warning("%s attempt %d failed for %s (%s) — retry in %ss",
                               fetcher_name, attempt + 1, url, exc, delay)
                time.sleep(delay)
    raise EngineError(f"{fetcher_name} failed for {url}: {last_error}")


def stealth_page(url: str, *, wait_selector: str | None = None,
                 timeout_ms: int = 60000, network_idle: bool = True) -> Page:
    """Render with the stealth browser profile (fingerprint spoofing)."""
    return _browser_fetch("StealthyFetcher", url, wait_selector=wait_selector,
                          timeout_ms=timeout_ms, network_idle=network_idle)


def dynamic_page(url: str, *, wait_selector: str | None = None,
                 timeout_ms: int = 60000, network_idle: bool = True) -> Page:
    """Render with plain headless Chromium (fallback to stealth profile)."""
    return _browser_fetch("DynamicFetcher", url, wait_selector=wait_selector,
                          timeout_ms=timeout_ms, network_idle=network_idle)
