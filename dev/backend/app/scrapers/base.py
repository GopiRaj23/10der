"""Scraper foundation.

Every portal scraper is a standalone class inheriting `BaseScraper`. Scrapers
NEVER raise out of `safe_scrape()` — failures are logged and returned so a
broken portal can't take down the scheduler or the API.

Fetching is powered by Scrapling (see `engine.py`): impersonated HTTP for
plain portals, stealth headless Chromium for JS/anti-bot ones. robots.txt and
politeness delays are enforced here, before any request leaves the box.
"""
from __future__ import annotations

import logging
import time
import urllib.robotparser
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from urllib.parse import urlparse

import httpx

from ..config import settings
from . import engine

logger = logging.getLogger(__name__)

_robots_cache: dict[str, urllib.robotparser.RobotFileParser | None] = {}


class ScraperError(Exception):
    """Recoverable scraper failure (network, parse, config)."""


class ScraperNotImplemented(ScraperError):
    """Stub scrapers raise this; logged as 'skipped', not 'failed'."""


@dataclass
class TenderRecord:
    """Normalised record every scraper must emit."""

    tender_ref_no: str
    title: str
    organisation: str | None = None
    department: str | None = None
    category: str | None = None          # works | goods | services
    state: str | None = None
    published_date: date | None = None
    closing_date: datetime | None = None
    estimated_value: float | None = None
    document_url: str | None = None
    raw_url: str | None = None
    description_text: str | None = None
    raw_html: str | None = field(default=None, repr=False)


class BaseScraper(ABC):
    """Abstract base. Subclasses set `portal_code` and implement `scrape()`."""

    portal_code: str = "base"
    user_agent = "TenderRadarBot/1.0 (+tender aggregation; contact admin)"

    def __init__(self, portal=None):
        self.portal = portal
        self.base_url = getattr(portal, "base_url", "")
        self.logger = logging.getLogger(f"scraper.{self.portal_code}")

    # --- public API ---------------------------------------------------------

    @abstractmethod
    def scrape(self, search_terms: list[str]) -> list[TenderRecord]:
        """Fetch & parse tenders. May raise ScraperError."""

    def safe_scrape(self, search_terms: list[str]) -> tuple[list[TenderRecord], str | None]:
        """Never raises. Returns (records, error_message)."""
        try:
            records = self.scrape(search_terms)
            return self._dedupe(records), None
        except ScraperNotImplemented as exc:
            self.logger.info("Skipped: %s", exc)
            return [], f"skipped: {exc}"
        except Exception as exc:  # noqa: BLE001 — scraper isolation by design
            self.logger.exception("Scrape failed for %s", self.portal_code)
            return [], str(exc)[:1000]

    # --- shared helpers -------------------------------------------------------

    @staticmethod
    def _dedupe(records: list[TenderRecord]) -> list[TenderRecord]:
        seen: set[str] = set()
        out = []
        for r in records:
            if r.tender_ref_no and r.tender_ref_no not in seen:
                seen.add(r.tender_ref_no)
                out.append(r)
        return out

    def robots_allowed(self, url: str) -> bool:
        """Honour robots.txt when RESPECT_ROBOTS_TXT is enabled."""
        if not settings.respect_robots_txt:
            return True
        origin = "{0.scheme}://{0.netloc}".format(urlparse(url))
        if origin not in _robots_cache:
            rp = urllib.robotparser.RobotFileParser()
            try:
                resp = httpx.get(f"{origin}/robots.txt", timeout=10,
                                 headers={"User-Agent": self.user_agent},
                                 follow_redirects=True, verify=False)
                if resp.status_code == 200:
                    rp.parse(resp.text.splitlines())
                    _robots_cache[origin] = rp
                else:
                    _robots_cache[origin] = None  # no robots file => allowed
            except Exception:
                _robots_cache[origin] = None
        rp = _robots_cache[origin]
        allowed = True if rp is None else rp.can_fetch(self.user_agent, url)
        if not allowed:
            self.logger.warning("robots.txt disallows %s — skipping", url)
        return allowed

    def _pre_fetch(self, url: str) -> None:
        """robots.txt gate + politeness delay, shared by every strategy."""
        if not self.robots_allowed(url):
            raise ScraperError(f"Blocked by robots.txt: {url}")
        time.sleep(settings.scrape_delay_seconds)

    def fetch_http(self, url: str) -> engine.Page:
        """Impersonated HTTP fetch (scrapling Fetcher / curl_cffi)."""
        self._pre_fetch(url)
        try:
            return engine.http_page(url)
        except engine.EngineError as exc:
            raise ScraperError(str(exc)) from exc

    def http_session(self):
        """Cookie-persistent session (context manager) for portals that need a
        real navigation flow (JSF/GePNIC session tokens)."""
        return engine.open_session()

    def session_get(self, sess, url: str) -> engine.Page:
        """GET inside an open session, with robots + politeness delay applied."""
        self._pre_fetch(url)
        try:
            resp = sess.get(url)
        except Exception as exc:  # noqa: BLE001 — curl/session errors vary
            raise ScraperError(f"session fetch failed for {url}: {exc}") from exc
        if resp.status >= 400:
            raise ScraperError(f"HTTP {resp.status} for {url}")
        return engine.Page(url=url, status=resp.status, html=resp.html_content)

    # --- parsing helpers ----------------------------------------------------

    DATE_FORMATS = (
        "%d-%b-%Y %I:%M %p", "%d-%b-%Y %H:%M", "%d-%b-%Y",
        "%d/%m/%Y %H:%M", "%d/%m/%Y", "%d-%m-%Y %H:%M", "%d-%m-%Y",
        "%Y-%m-%d %H:%M:%S", "%Y-%m-%d",
    )

    @classmethod
    def parse_dt(cls, value: str | None) -> datetime | None:
        if not value:
            return None
        value = value.strip()
        for fmt in cls.DATE_FORMATS:
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        try:
            from dateutil import parser as duparser
            return duparser.parse(value, dayfirst=True)
        except Exception:
            return None

    @classmethod
    def parse_date(cls, value: str | None) -> date | None:
        dt = cls.parse_dt(value)
        return dt.date() if dt else None

    @staticmethod
    def parse_value(value: str | None) -> float | None:
        if not value:
            return None
        import re
        cleaned = re.sub(r"[^\d.]", "", str(value))
        try:
            num = float(cleaned) if cleaned else None
        except ValueError:
            return None
        if num is None:
            return None
        text = str(value).lower()
        if "crore" in text or "cr" in text.split():
            num *= 1e7
        elif "lakh" in text or "lac" in text:
            num *= 1e5
        return num


class BrowserScraper(BaseScraper):
    """Base for JS-heavy / bot-protected portals: renders pages with scrapling's
    stealth headless Chromium (fingerprint spoofing), falling back to a plain
    Chromium render.

    Needs a one-time `scrapling install` (free browser download). When the
    browser is missing the scraper reports a clean error instead of crashing
    the worker.
    """

    portal_code = "browser-base"

    def render_page(self, url: str, wait_selector: str | None = None,
                    timeout_ms: int = 60000) -> engine.Page:
        self._pre_fetch(url)
        try:
            return engine.stealth_page(url, wait_selector=wait_selector,
                                       timeout_ms=timeout_ms)
        except engine.StealthUnavailable as exc:
            raise ScraperError(str(exc)) from exc
        except engine.EngineError as exc:
            self.logger.warning("Stealth render failed (%s) — trying plain "
                                "Chromium", exc)
        try:
            return engine.dynamic_page(url, wait_selector=wait_selector,
                                       timeout_ms=timeout_ms)
        except engine.EngineError as exc:
            raise ScraperError(str(exc)) from exc

    def scrape(self, search_terms: list[str]) -> list[TenderRecord]:
        raise ScraperNotImplemented(f"{self.portal_code} browser scraper not implemented")
