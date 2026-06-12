"""GeM (Government e-Marketplace, gem.gov.in) scraper.

Reference implementation #2. GeM's public bid list lives at
bidplus.gem.gov.in/all-bids and is rendered client-side behind bot
protection, so it needs a real browser:

 1. Scrapling stealth headless-Chromium (fingerprint spoofing) — primary
 2. Plain headless-Chromium render — fallback (handled by BrowserScraper)

Requires the one-time free `scrapling install` browser download.
"""
from __future__ import annotations

import re

from .base import BrowserScraper, ScraperError, TenderRecord

BID_LIST_PATH = "/all-bids"

_BID_NO_RE = re.compile(r"GEM/\d{4}/B/\d+")


class GeMScraper(BrowserScraper):
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
        page = self.render_page(url, wait_selector=".card", timeout_ms=60000)
        records = self._parse_bid_cards(page, url)
        if not records:
            raise ScraperError("GeM: no bid cards found after rendering")
        return records

    # --- parsing -------------------------------------------------------------

    def _bid_doc_url(self, bid_no: str) -> str | None:
        # GEM/2026/B/123456 -> showbidDocument/123456
        m = re.search(r"/B/(\d+)", bid_no or "")
        return f"{self.bids_base}/showbidDocument/{m.group(1)}" if m else None

    def _parse_bid_cards(self, page, page_url: str) -> list[TenderRecord]:
        doc = page.select()
        records: list[TenderRecord] = []
        for card in doc.css(".card"):
            # collapse interior newlines/runs so the label regexes can span them
            text = " ".join(card.get_all_text(" ", strip=True).split())
            bid_link = card.css("a.bid_no_hover").first
            bid_no = bid_link.get_all_text(strip=True) if bid_link is not None else None
            if not bid_no or not _BID_NO_RE.search(bid_no):
                m = _BID_NO_RE.search(text)
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
                raw_html=card.html_content[:20000],
            ))
        return records
