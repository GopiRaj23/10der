"""CPPP (Central Public Procurement Portal, eprocure.gov.in) scraper.

Reference implementation #1. The same NIC "GePNIC" software powers most
central/state portals, so the parsing core lives in `NICGenericScraper` and
is reused by every NIC-based portal (etenders.gov.in, tntenders.gov.in, ...).

Strategy (all free, via Scrapling):
 1. Impersonated HTTP fetch (Chrome TLS fingerprint) + table parse
 2. Stealth headless-Chromium render (when the portal's WAF blocks plain HTTP)
"""
from __future__ import annotations

from . import engine
from .base import BaseScraper, ScraperError, TenderRecord


class NICGenericScraper(BaseScraper):
    """Shared implementation for GePNIC/NIC eProcurement portals."""

    portal_code = "nic-generic"
    app_path = "/nicgep/app"          # CPPP overrides to /eprocure/app
    max_pages = 3

    def list_url(self, page: int = 1) -> str:
        url = f"{self.base_url.rstrip('/')}{self.app_path}?page=FrontEndLatestActiveTenders&service=page"
        if page > 1:
            # NIC pagination uses a component link with the page number last
            url = (f"{self.base_url.rstrip('/')}{self.app_path}"
                   f"?component=%24TablePages.linkPage&page=FrontEndLatestActiveTenders"
                   f"&service=direct&session=T&sp=AFrontEndLatestActiveTenders%2Ctable&sp={page}")
        return url

    # --- main entry -----------------------------------------------------------

    def scrape(self, search_terms: list[str]) -> list[TenderRecord]:
        records: list[TenderRecord] = []
        last_error: Exception | None = None
        for page in range(1, self.max_pages + 1):
            url = self.list_url(page)
            try:
                page_records = self._scrape_page(url)
            except Exception as exc:  # keep what we have from earlier pages
                last_error = exc
                self.logger.warning("Page %s failed: %s", page, exc)
                break
            if not page_records:
                break
            records.extend(page_records)
        if not records and last_error:
            raise ScraperError(str(last_error))
        return self._filter_by_terms(records, search_terms)

    def _scrape_page(self, url: str) -> list[TenderRecord]:
        # 1) Impersonated HTTP (fast path)
        http_error: Exception | None = None
        try:
            page = self.fetch_http(url)
            records = self._parse_nic_table(page, url)
            if records:
                return records
        except ScraperError as exc:
            http_error = exc
            self.logger.warning("HTTP fetch failed (%s) — trying stealth browser", exc)

        # 2) Stealth browser render (WAF/JS wall)
        try:
            rendered = engine.stealth_page(url, wait_selector="table", timeout_ms=60000)
        except engine.StealthUnavailable as exc:
            # No browser installed: surface the most useful error
            raise ScraperError(str(http_error or exc)) from exc
        except engine.EngineError as exc:
            raise ScraperError(str(http_error or exc)) from exc
        return self._parse_nic_table(rendered, url)

    # --- parsing ---------------------------------------------------------------

    def _parse_nic_table(self, page: engine.Page, page_url: str) -> list[TenderRecord]:
        """Parse the GePNIC 'Latest Active Tenders' list table.

        Columns: S.No | e-Published Date | Closing Date | Opening Date |
                 Title and Ref.No./Tender ID | Organisation Chain
        """
        doc = page.select()
        table = doc.css("table#table").first or doc.css("table.list_table").first
        if table is None:
            # Some instances render the list inside nested tables
            for cand in doc.css("table"):
                head = " ".join(cand.get_all_text(" ", strip=True).split())[:300].lower()
                if "e-published" in head and "closing" in head:
                    table = cand
                    break
        if table is None:
            return []

        records: list[TenderRecord] = []
        for row in table.css("tr"):
            cells = row.css("td")
            if len(cells) < 6:
                continue
            # collapse interior newlines/whitespace runs inside each cell
            texts = [" ".join(c.get_all_text(" ", strip=True).split()) for c in cells]
            if not texts[0].rstrip(".").isdigit():
                continue  # header / pagination rows
            title_cell = cells[4]
            link = title_cell.css("a").first
            title_text = texts[4]
            # Title cell looks like: "Supply of ... [ref-no][tender-id]"
            ref_no = title_text
            title = title_text
            if "[" in title_text:
                title = title_text.split("[")[0].strip()
                refs = [p.strip("[] ") for p in title_text.split("[")[1:]]
                ref_no = refs[-1] if refs else title_text
            href = link.attrib.get("href") if link is not None else None
            if href and href.startswith("/"):
                href = f"{self.base_url.rstrip('/')}{href}"
            records.append(TenderRecord(
                tender_ref_no=(ref_no or title)[:160],
                title=title or title_text,
                organisation=texts[5][:300] or None,
                published_date=self.parse_date(texts[1]),
                closing_date=self.parse_dt(texts[2]),
                document_url=href or page_url,
                raw_url=page_url,
                state=getattr(self.portal, "state", None),
                raw_html=row.html_content[:20000],
            ))
        return records

    def _filter_by_terms(self, records: list[TenderRecord],
                         search_terms: list[str]) -> list[TenderRecord]:
        """List pages aren't keyword-searchable on NIC portals; we fetch the
        latest tenders and keep everything — per-user keyword relevance is
        computed downstream. (Kept as a hook for portals with server-side
        search.)"""
        return records


class CPPPScraper(NICGenericScraper):
    """Central Public Procurement Portal — eprocure.gov.in."""

    portal_code = "cppp"
    app_path = "/eprocure/app"
    max_pages = 3
