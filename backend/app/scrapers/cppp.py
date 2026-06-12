"""CPPP (Central Public Procurement Portal, eprocure.gov.in) scraper.

Reference implementation #1. The same NIC "GePNIC" software powers most
central/state portals, so the parsing core lives in `NICGenericScraper` and
is reused by every NIC-based portal (etenders.gov.in, tntenders.gov.in, ...).

Strategy:
 1. Firecrawl /scrape with a structured-extract schema (primary)
 2. Direct httpx fetch + BeautifulSoup table parse (fallback)
"""
from __future__ import annotations

from bs4 import BeautifulSoup

from .base import BaseScraper, ScraperError, TenderRecord
from .firecrawl_client import FirecrawlNotConfigured, firecrawl

# Structured-extract schema sent to Firecrawl for NIC list pages.
NIC_EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "tenders": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "tender_id": {"type": "string"},
                    "title": {"type": "string"},
                    "organisation": {"type": "string"},
                    "published_date": {"type": "string"},
                    "closing_date": {"type": "string"},
                    "opening_date": {"type": "string"},
                    "document_url": {"type": "string"},
                },
                "required": ["tender_id", "title"],
            },
        }
    },
    "required": ["tenders"],
}


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
            except Exception as exc:  # try next strategy/page, keep what we have
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
        # 1) Firecrawl structured extraction
        try:
            data = firecrawl.scrape(
                url,
                formats=["html"],
                extract_schema=NIC_EXTRACT_SCHEMA,
                extract_prompt="Extract every tender row from the latest active tenders table.",
            )
            extracted = (data.get("extract") or {}).get("tenders") or []
            html = data.get("html")
            if extracted:
                return [self._record_from_extract(t, url, html) for t in extracted]
            if html:
                return self._parse_nic_table(html, url)
        except FirecrawlNotConfigured:
            self.logger.info("Firecrawl not configured — falling back to direct fetch")
        except Exception as exc:
            self.logger.warning("Firecrawl failed (%s) — falling back to direct fetch", exc)

        # 2) Direct fetch + parse
        resp = self.http_get(url)
        return self._parse_nic_table(resp.text, url)

    # --- parsing ---------------------------------------------------------------

    def _record_from_extract(self, t: dict, page_url: str, raw_html: str | None) -> TenderRecord:
        return TenderRecord(
            tender_ref_no=(t.get("tender_id") or "").strip()[:160],
            title=(t.get("title") or "").strip(),
            organisation=(t.get("organisation") or "").strip() or None,
            published_date=self.parse_date(t.get("published_date")),
            closing_date=self.parse_dt(t.get("closing_date")),
            document_url=t.get("document_url") or page_url,
            raw_url=page_url,
            state=getattr(self.portal, "state", None),
            raw_html=raw_html,
        )

    def _parse_nic_table(self, html: str, page_url: str) -> list[TenderRecord]:
        """Parse the GePNIC 'Latest Active Tenders' list table.

        Columns: S.No | e-Published Date | Closing Date | Opening Date |
                 Title and Ref.No./Tender ID | Organisation Chain
        """
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table", id="table") or soup.find("table", class_="list_table")
        if table is None:
            # Some instances render the list inside nested tables
            for cand in soup.find_all("table"):
                head = cand.get_text(" ", strip=True)[:300].lower()
                if "e-published" in head and "closing" in head:
                    table = cand
                    break
        if table is None:
            return []

        records: list[TenderRecord] = []
        for row in table.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 6:
                continue
            texts = [c.get_text(" ", strip=True) for c in cells]
            if not texts[0].rstrip(".").isdigit():
                continue  # header / pagination rows
            title_cell = cells[4]
            link = title_cell.find("a")
            title_text = title_cell.get_text(" ", strip=True)
            # Title cell looks like: "Supply of ... [ref-no][tender-id]"
            ref_no = title_text
            title = title_text
            if "[" in title_text:
                title = title_text.split("[")[0].strip()
                refs = [p.strip("[] ") for p in title_text.split("[")[1:]]
                ref_no = refs[-1] if refs else title_text
            href = link.get("href") if link else None
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
                raw_html=str(row)[:20000],
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
