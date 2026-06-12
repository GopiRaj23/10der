"""Live-scrape test harness — verify a portal returns REAL tenders.

Run this from a machine that can reach the portals (i.e. your local machine,
NOT a locked-down CI/cloud box). It bypasses DEMO_MODE and calls the real
scraper directly so you can confirm live data flows before trusting the app.

Usage:
    python -m app.scrapers.test_live              # list portals you can test
    python -m app.scrapers.test_live cppp         # test one portal
    python -m app.scrapers.test_live cppp gem tn  # test several
    python -m app.scrapers.test_live --dump cppp  # + inspect/save the raw HTML

What it prints: how the scraper was resolved (real vs stub), whether the
stealth browser is installed, the number of tenders found, and sample titles.
With --dump (or when 0 rows are parsed) it also fetches the raw list page and
reports what came back, so a portal that returns a session/JS shell instead of
the tender table can be diagnosed.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from sqlalchemy import select

from ..config import settings
from ..database import SessionLocal
from ..models import PortalSource
from .registry import SCRAPERS
from .stubs import _StubScraper

# Markers that tell us WHAT the portal returned when the table won't parse.
_MARKERS = {
    "tender list heading": ("latest active tenders", "tenders by closing date",
                            "search active tenders"),
    "table column headers": ("e-published", "closing date", "tender id",
                             "organisation chain"),
    "empty result": ("no records found", "no tenders", "0 records"),
    "session/redirect": ("session expired", "invalid request", "session has",
                         "page has expired"),
    "captcha/anti-bot": ("captcha", "are you human", "verify you are",
                         "cloudflare", "checking your browser"),
    "JS shell": ("please enable javascript", "noscript", "window.location"),
}


def _diagnose(scraper, portal) -> None:
    """Fetch the raw list page (the same way the scraper does) and report what
    actually came back."""
    nic = hasattr(scraper, "home_url") and hasattr(scraper, "list_url")
    url = scraper.list_url(1) if nic else portal.base_url
    print(f"\n  ── HTML diagnosis ── {url}")
    try:
        if nic:
            page = scraper.fetch_session([scraper.base_url, scraper.home_url()], url)
        else:
            page = scraper.fetch_http(url)
    except Exception as exc:  # noqa: BLE001
        print(f"  could not fetch for diagnosis: {exc}")
        return
    html = page.html or ""
    doc = page.select()
    title = doc.css("title").first
    title = title.get_all_text(strip=True) if title is not None else "—"
    n_tables = len(doc.css("table"))
    n_rows = len(doc.css("tr"))
    low = html.lower()
    print(f"  HTTP {page.status} | {len(html):,} bytes | <title>: {title[:70]}")
    print(f"  tables: {n_tables} | <tr> rows: {n_rows}")
    found = [label for label, needles in _MARKERS.items()
             if any(n in low for n in needles)]
    print(f"  markers present: {', '.join(found) if found else 'none of the known ones'}")
    # Save full HTML to the storage volume for sharing / deeper inspection
    out_dir = Path(settings.storage_dir) / "debug"
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / f"{portal.code}.html"
        out_file.write_text(html, encoding="utf-8")
        # In the Docker image the app lives at /app and storage_dir is relative.
        container_path = out_file if out_file.is_absolute() else Path("/app") / out_file
        print(f"  saved full HTML → {out_file}")
        print(f"  copy it out with:  docker compose cp backend:{container_path} ./{portal.code}.html")
    except Exception as exc:  # noqa: BLE001
        print(f"  (could not save HTML: {exc})")
    # A short visible-text preview is usually enough to see the problem
    text = " ".join(doc.get_all_text(" ", strip=True).split())
    print(f"  text preview: {text[:300]}")


def _print_portals(db) -> None:
    print("\nPortals available to test (code — name — scraper):")
    for p in db.scalars(select(PortalSource)
                        .order_by(PortalSource.portal_group, PortalSource.code)).all():
        cls = SCRAPERS.get(p.code)
        kind = cls.__name__ if cls else "—(stub)"
        print(f"  {p.code:<14} {p.name[:42]:<42} {kind}")
    print("\nExample:  python -m app.scrapers.test_live cppp gem\n")


def _test_one(db, code: str, dump: bool = False) -> None:
    portal = db.scalar(select(PortalSource).where(PortalSource.code == code))
    print("\n" + "=" * 72)
    if not portal:
        print(f"✗ Unknown portal code: {code!r}")
        return
    cls = SCRAPERS.get(code)
    print(f"Portal : {portal.name}  ({portal.code})")
    print(f"URL    : {portal.base_url}")
    if cls is None or issubclass(cls, _StubScraper):
        print(f"Scraper: {cls.__name__ if cls else 'none'}  — STUB (not implemented, "
              "returns nothing). Custom-platform portal.")
        return
    from .engine import stealth_browser_ready
    print(f"Scraper: {cls.__name__}  (real, engine: scrapling)")
    print(f"Stealth browser installed: {stealth_browser_ready()}  "
          f"| DEMO_MODE={settings.demo_mode}")

    scraper = cls(portal)
    print("Fetching live data … (this hits the real portal)")
    records, error = scraper.safe_scrape([])  # empty terms = fetch latest tenders
    print(f"\nResult : {len(records)} tender(s) found"
          + (f"   | note: {error}" if error else ""))
    for r in records[:8]:
        closing = r.closing_date.strftime("%d-%b-%Y") if r.closing_date else "—"
        print(f"  • [{r.tender_ref_no[:28]:<28}] closes {closing}  {r.title[:60]}")
    if records:
        print(f"  … {max(0, len(records) - 8)} more")
    # Diagnose whenever nothing was scraped (or when explicitly asked)
    if dump or not records:
        _diagnose(scraper, portal)


def main() -> None:
    logging.basicConfig(level=logging.INFO,
                        format="%(levelname)s %(name)s — %(message)s")
    args = sys.argv[1:]
    dump = "--dump" in args
    codes = [a for a in args if not a.startswith("-")]
    db = SessionLocal()
    try:
        if not codes:
            _print_portals(db)
            return
        if settings.demo_mode:
            print("\nℹ DEMO_MODE is ON — the app itself serves sample data. This test "
                  "bypasses it and calls the REAL scraper so you can verify live "
                  "access before flipping DEMO_MODE=false.")
        for code in codes:
            _test_one(db, code, dump=dump)
        print("\n" + "=" * 72)
        from .engine import stealth_browser_ready
        if not stealth_browser_ready():
            print("Tip: run `scrapling install` once (free browser download) to unlock\n"
                  "     GeM and other JS-heavy portals, and to give NIC portals a\n"
                  "     stealth-browser fallback when the list is JS/session-rendered.\n")
    finally:
        db.close()


if __name__ == "__main__":
    main()

