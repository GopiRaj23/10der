"""GeM (Government e-Marketplace, gem.gov.in) scraper.

Reference implementation #2. GeM's public bid list lives at
bidplus.gem.gov.in/all-bids and is rendered client-side, so the order of
attack is:

 1. Firecrawl /scrape with structured extraction (handles JS rendering)
 2. Playwright headless-Chromium render + BeautifulSoup parse (fallback)
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from .base import PlaywrightScraper, ScraperError, TenderRecord
from .firecrawl_client import FirecrawlNotConfigured, firecrawl

GEM_EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "bids": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "bid_no": {"type": "string"},
                    "items": {"type": "string"},
                    "quantity": {"type": "string"},
                    "department": {"type": "string"},
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"},
                },
                "required": ["bid_no"],
            },
        }
    },
    "required": ["bids"],
}

BID_LIST_PATH = "/all-bids"


class GeMScraper(PlaywrightScraper):
    portal_code = "gem"
    max_pages = 2

    @property
    def bids_base(self) -> str:
        # bid listing lives on the bidplus subdomain
        if "bidplus" in self.base_url:
            return self.base_url.rstrip("/")
        return "https://bidplus.gem.gov.in"

    def scrape(self, search_terms: list[str]) -> list[TenderRecord]:
        url = f"{self.bids_base}{BID_LIST_PATH}"
        # 1) Firecrawl (renders JS, returns structured bids)
        try:
            data = firecrawl.scrape(
                url,
                formats=["html"],
                extract_schema=GEM_EXTRACT_SCHEMA,
                extract_prompt="Extract all bid cards: bid number, item names, "
                               "quantity, department, start and end dates.",
                wait_for=4000,
            )
            bids = (data.get("extract") or {}).get("bids") or []
            html = data.get("html")
            if bids:
                return [self._record_from_extract(b, url, html) for b in bids]
            if html:
                records = self._parse_bid_cards(html, url)
                if records:
                    return records
        except FirecrawlNotConfigured:
            self.logger.info("Firecrawl not configured — trying Playwright fallback")
        except Exception as exc:
            self.logger.warning("Firecrawl failed (%s) — trying Playwright fallback", exc)

        # 2) Playwright render
        html = self.render_page(url, wait_selector=".card", timeout_ms=60000)
        records = self._parse_bid_cards(html, url)
        if not records:
            raise ScraperError("GeM: no bid cards found after rendering")
        return records

    # --- parsing -------------------------------------------------------------

    def _record_from_extract(self, b: dict, page_url: str, raw_html: str | None) -> TenderRecord:
        bid_no = (b.get("bid_no") or "").strip()
        return TenderRecord(
            tender_ref_no=bid_no[:160],
            title=(b.get("items") or bid_no).strip()[:500],
            organisation=(b.get("department") or "").strip()[:300] or None,
            category="goods",
            published_date=self.parse_date(b.get("start_date")),
            closing_date=self.parse_dt(b.get("end_date")),
            description_text=(f"Items: {b.get('items', '')} | "
                              f"Quantity: {b.get('quantity', '')}").strip(" |"),
            document_url=self._bid_doc_url(bid_no) or page_url,
            raw_url=page_url,
            raw_html=raw_html,
        )

    def _bid_doc_url(self, bid_no: str) -> str | None:
        # GEM/2026/B/123456 -> showbidDocument/123456
        m = re.search(r"/B/(\d+)", bid_no or "")
        return f"{self.bids_base}/showbidDocument/{m.group(1)}" if m else None

    def _parse_bid_cards(self, html: str, page_url: str) -> list[TenderRecord]:
        soup = BeautifulSoup(html, "html.parser")
        records: list[TenderRecord] = []
        for card in soup.select(".card"):
            text = card.get_text(" ", strip=True)
            bid_link = card.select_one("a.bid_no_hover") or card.find(
                "a", string=re.compile(r"GEM/\d{4}"))
            bid_no = bid_link.get_text(strip=True) if bid_link else None
            if not bid_no:
                m = re.search(r"GEM/\d{4}/B/\d+", text)
                bid_no = m.group(0) if m else None
            if not bid_no:
                continue

            def grab(label: str) -> str | None:
                m = re.search(rf"{label}\s*:?\s*(.+?)(?=(?:Items|Quantity|Department|"
                              rf"Start Date|End Date|Address)\s*:|$)", text, re.I)
                return m.group(1).strip() if m else None

            items = grab("Items")
            records.append(TenderRecord(
                tender_ref_no=bid_no[:160],
                title=(items or bid_no)[:500],
                organisation=(grab("Department Name And Address")
                              or grab("Department") or "")[:300] or None,
                category="goods",
                published_date=self.parse_date(grab("Start Date")),
                closing_date=self.parse_dt(grab("End Date")),
                description_text=text[:2000],
                document_url=self._bid_doc_url(bid_no) or page_url,
                raw_url=page_url,
                raw_html=str(card)[:20000],
            ))
        return records
