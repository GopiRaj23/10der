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
With --dump (or when 0 rows are parsed) it replays the scraper's HTTP flow
step by step — home page, whether the 'Latest Active Tenders' link was found,
the followed page — then a per-table breakdown showing which table (if any)
contains tender-shaped rows, so "parser needs fixing" vs "data is JS-rendered,
browser needed" can be told apart conclusively.
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

def _table_report(doc) -> None:
    """Per-table breakdown: which (if any) table holds tender-shaped rows —
    rows with ≥5 cells of which ≥2 parse as dates. This is the decisive
    signal: 'tender-like rows in table N' means the parser needs adjusting;
    'no tender-like rows anywhere' means the data isn't in the HTML at all
    (JS-rendered → browser needed)."""
    from .base import BaseScraper

    tables = doc.css("table")
    print(f"  per-table breakdown ({len(tables)} tables):")
    any_tenderlike = False
    for i, t in enumerate(tables[:30]):
        rows = t.css("tr")
        max_td, date_rows, sample = 0, 0, None
        for r in rows:
            tds = [" ".join(c.get_all_text(" ", strip=True).split()) for c in r.css("td")]
            max_td = max(max_td, len(tds))
            if len(tds) >= 5:
                dateish = sum(1 for c in tds if c and BaseScraper.parse_dt(c))
                if dateish >= 2:
                    date_rows += 1
                    if sample is None:
                        sample = tds
        flag = "   ← tender-like rows" if date_rows else ""
        if date_rows or len(rows) > 2:   # skip layout noise
            tid = t.attrib.get("id") or t.attrib.get("class") or "-"
            print(f"    table[{i:>2}] id/class={str(tid)[:18]:<18} rows={len(rows):<4} "
                  f"max_td={max_td:<3} tender_rows={date_rows}{flag}")
        if sample and not any_tenderlike:
            any_tenderlike = True
            print(f"      sample row: {' | '.join(c[:30] for c in sample[:7])}")
    if not any_tenderlike:
        print("    → NO tender-shaped rows in any table: the list is NOT in this "
              "HTML (JS-rendered or wrong page).")


def _shell_report(html: str, doc) -> None:
    """Detect redirect mechanisms that would explain a bounced page."""
    low = html.lower()
    hints = []
    for f in doc.css("frame, iframe"):
        src = f.attrib.get("src")
        if src:
            hints.append(f"frame/iframe → {src[:80]}")
    if 'http-equiv="refresh"' in low or "http-equiv='refresh'" in low:
        hints.append("meta-refresh redirect present")
    for marker in ("location.replace", "location.href", "window.location"):
        if marker in low:
            hints.append(f"JS redirect code present ({marker})")
            break
    if "captcha" in low:
        hints.append("the word 'captcha' appears (may be just the search form)")
    if hints:
        print("  page mechanisms: " + "; ".join(hints))


def _save_html(portal_code: str, html: str) -> None:
    out_dir = Path(settings.storage_dir) / "debug"
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / f"{portal_code}.html"
        out_file.write_text(html, encoding="utf-8")
        # In the Docker image the app lives at /app and storage_dir is relative.
        container_path = out_file if out_file.is_absolute() else Path("/app") / out_file
        print(f"  saved full HTML → {out_file}")
        print(f"  copy it out with:  docker compose cp backend:{container_path} ./{portal_code}.html")
    except Exception as exc:  # noqa: BLE001
        print(f"  (could not save HTML: {exc})")


def _page_summary(label: str, page) -> None:
    doc = page.select()
    title = doc.css("title").first
    title = title.get_all_text(strip=True) if title is not None else "—"
    print(f"  {label}: HTTP {page.status} | {len(page.html or ''):,} bytes | "
          f"<title>: {title[:60]}")


def _diagnose(scraper, portal) -> None:
    """Replay the scraper's own fetch flow step by step and report what each
    stage actually returned."""
    print("\n  ── diagnosis (replaying the scraper's HTTP flow) ──")
    nic = hasattr(scraper, "home_candidates")
    try:
        if nic:
            with scraper.http_session() as sess:
                list_page = None
                for home in scraper.home_candidates():
                    try:
                        home_page = scraper.session_get(sess, home)
                    except Exception as exc:  # noqa: BLE001
                        print(f"  home {home} → failed: {exc}")
                        continue
                    _page_summary(f"home {home}", home_page)
                    link = scraper._find_list_link(home_page)
                    if link:
                        print(f"  ✓ 'Latest Active Tenders' link found → {link[:110]}")
                        list_page = scraper.session_get(sess, link)
                        break
                    print("  ✗ no 'Latest Active Tenders' link on this page")
                if list_page is None:
                    print(f"  falling back to direct list URL: {scraper.list_url(1)}")
                    list_page = scraper.session_get(sess, scraper.list_url(1))
            page = list_page
        else:
            page = scraper.fetch_http(portal.base_url)
    except Exception as exc:  # noqa: BLE001
        print(f"  could not fetch for diagnosis: {exc}")
        return

    _page_summary("final page", page)
    doc = page.select()
    _shell_report(page.html or "", doc)
    _table_report(doc)
    _save_html(portal.code, page.html or "")
    text = " ".join(doc.get_all_text(" ", strip=True).split())
    print(f"  text preview: {text[:240]}")


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

