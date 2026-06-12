"""Live-scrape test harness — verify a portal returns REAL tenders.

Run this from a machine that can reach the portals (i.e. your local machine,
NOT a locked-down CI/cloud box). It bypasses DEMO_MODE and calls the real
scraper directly so you can confirm live data flows before trusting the app.

Usage:
    python -m app.scrapers.test_live              # list portals you can test
    python -m app.scrapers.test_live cppp         # test one portal
    python -m app.scrapers.test_live cppp gem tn  # test several

What it prints: how the scraper was resolved (real vs stub), whether the
stealth browser is installed, the number of tenders found, and sample titles.
"""
from __future__ import annotations

import logging
import sys

from sqlalchemy import select

from ..config import settings
from ..database import SessionLocal
from ..models import PortalSource
from .registry import SCRAPERS
from .stubs import _StubScraper


def _print_portals(db) -> None:
    print("\nPortals available to test (code — name — scraper):")
    for p in db.scalars(select(PortalSource)
                        .order_by(PortalSource.portal_group, PortalSource.code)).all():
        cls = SCRAPERS.get(p.code)
        kind = cls.__name__ if cls else "—(stub)"
        print(f"  {p.code:<14} {p.name[:42]:<42} {kind}")
    print("\nExample:  python -m app.scrapers.test_live cppp gem\n")


def _test_one(db, code: str) -> None:
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
    elif not error:
        print("  (parser ran but found 0 rows — the portal markup may have changed)")


def main() -> None:
    logging.basicConfig(level=logging.INFO,
                        format="%(levelname)s %(name)s — %(message)s")
    codes = [a for a in sys.argv[1:] if not a.startswith("-")]
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
            _test_one(db, code)
        print("\n" + "=" * 72)
        from .engine import stealth_browser_ready
        if not stealth_browser_ready():
            print("Tip: run `scrapling install` once (free browser download) to unlock\n"
                  "     GeM and other JS-heavy portals, and to give NIC portals a\n"
                  "     stealth-browser fallback when their WAF blocks plain HTTP.\n")
    finally:
        db.close()


if __name__ == "__main__":
    main()
