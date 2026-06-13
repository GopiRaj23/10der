"""CPPP (Central Public Procurement Portal, eprocure.gov.in) scraper.

Reference implementation #1. The same NIC "GePNIC" software powers most
central/state portals, so the parsing core lives in `NICGenericScraper` and
is reused by every NIC-based portal (etenders.gov.in, tntenders.gov.in, ...).

GePNIC is an old Tapestry/JSF app: deep-linking the tender list directly often
bounces to the portal home page, and the working list URL carries a session
token. So the scraper browses like a user, all over plain HTTP (free, no
browser):

 1. ONE cookie-persistent session: open the portal home, find the real
    "Latest Active Tenders" link (it embeds the session token), follow it,
    parse; follow the numbered `linkPage` pagination links in-session.
 2. Stealth headless-Chromium render — only if the HTTP flow yields no rows
    (e.g. the instance renders the list with JavaScript).
"""
from __future__ import annotations

import re
from urllib.parse import urljoin

from . import engine
from .base import BaseScraper, ScraperError, TenderRecord

# Anchor texts that lead to the latest-tenders list, tried in order.
LIST_LINK_TEXTS = ("latest active tenders", "latest tenders")


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

    def home_candidates(self) -> list[str]:
        """Pages likely to carry the 'Latest Active Tenders' link, tried in order."""
        base = self.base_url.rstrip("/")
        return [self.base_url, f"{base}{self.app_path}"]

    # --- main entry -----------------------------------------------------------

    def scrape(self, search_terms: list[str]) -> list[TenderRecord]:
        records: list[TenderRecord] = []
        flow_error: Exception | None = None
        fetched_ok = False
        try:
            records, fetched_ok = self._scrape_via_session()
        except ScraperError as exc:
            flow_error = exc
            self.logger.warning("HTTP session flow failed (%s) — trying stealth "
                                "browser", exc)
        if records:
            return self._filter_by_terms(records, search_terms)
        if fetched_ok and flow_error is None:
            self.logger.info("HTTP flow OK (200) but 0 tender rows parsed — "
                             "trying stealth browser render")

        # Browser fallback: GePNIC requires JavaScript (the no-JS path is
        # bounced to an "eTender System Exception / enable javascript" page), so
        # render the human flow — home → list — in one stealth-browser session.
        # The page's own JS establishes the session and loads the tender table.
        url = self.list_url(1)
        nav = [*self.home_candidates(), url]
        try:
            rendered = engine.browser_session_pages(nav, timeout_ms=60000)
        except engine.StealthUnavailable as exc:
            raise ScraperError(
                "this portal requires JavaScript — GePNIC serves the tender list "
                "only to a real browser (the no-JS path returns an 'enable "
                "javascript' error). Enable the free stealth browser: "
                "INSTALL_BROWSER=true + rebuild (Docker) or `scrapling install` "
                "(local)."
            ) from exc
        except engine.EngineError as exc:
            raise ScraperError(str(flow_error or exc)) from exc
        records = self._parse_nic_table(rendered, url)
        if not records:
            raise ScraperError(
                "browser-rendered the list page but still found no tender rows "
                "— the portal markup may have changed (run test_live --dump)"
            )
        return self._filter_by_terms(records, search_terms)

    # --- HTTP session flow ------------------------------------------------------

    def _scrape_via_session(self) -> tuple[list[TenderRecord], bool]:
        """Browse home → list link → pagination inside one cookie session.
        Returns (records, fetched_ok) where fetched_ok means at least one page
        came back HTTP 200 (i.e. network + impersonation are fine)."""
        records: list[TenderRecord] = []
        fetched_ok = False
        with self.http_session() as sess:
            list_page: engine.Page | None = None
            for home in self.home_candidates():
                try:
                    home_page = self.session_get(sess, home)
                    fetched_ok = True
                except ScraperError as exc:
                    self.logger.debug("home candidate %s failed: %s", home, exc)
                    continue
                link = self._find_list_link(home_page)
                if link:
                    self.logger.info("Following list link found on %s", home)
                    list_page = self._get_list(sess, link)
                    break
            if list_page is None:
                # No link found — request the canonical list URL in-session
                # (the session cookie alone is enough on some instances).
                list_page = self._get_list(sess, self.list_url(1))
                fetched_ok = True

            page_records = self._parse_nic_table(list_page, list_page.url)
            records.extend(page_records)
            pages = 1
            current = list_page
            while page_records and pages < self.max_pages:
                next_url = self._next_page_url(current, pages + 1)
                if not next_url:
                    break
                current = self._get_list(sess, next_url)
                page_records = self._parse_nic_table(current, current.url)
                records.extend(page_records)
                pages += 1
        return records, fetched_ok

    def _get_list(self, sess, url: str) -> engine.Page:
        """Fetch a list/pagination page and follow any meta-refresh bounce — the
        `service=page` URL returns a refresh stub pointing at the real
        session-tokenised list (`service=direct&session=T&...`)."""
        return self._follow_meta_refresh(sess, self.session_get(sess, url))

    def _follow_meta_refresh(self, sess, page: engine.Page,
                             max_hops: int = 3) -> engine.Page:
        seen = {page.url}
        for _ in range(max_hops):
            target = self._meta_refresh_target(page)
            if not target or target in seen:
                break
            seen.add(target)
            self.logger.info("Following meta-refresh → %s", target)
            page = self.session_get(sess, target)
        return page

    @staticmethod
    def _meta_refresh_target(page: engine.Page) -> str | None:
        """Extract the URL from <meta http-equiv="refresh" content="N;url=...">."""
        doc = page.select()
        for m in doc.css("meta"):
            if (m.attrib.get("http-equiv") or "").lower() != "refresh":
                continue
            content = m.attrib.get("content") or ""
            hit = re.search(r"url\s*=\s*['\"]?([^'\"]+)", content, re.I)
            if hit:
                return urljoin(page.url, hit.group(1).strip())
        return None

    def _find_list_link(self, page: engine.Page) -> str | None:
        """Find the 'Latest Active Tenders' anchor — its href carries the
        Tapestry session token the list page needs."""
        doc = page.select()
        for wanted in LIST_LINK_TEXTS:
            for a in doc.css("a"):
                href = a.attrib.get("href")
                if not href or href.lower().startswith(("javascript:", "#", "mailto:")):
                    continue
                text = " ".join(a.get_all_text(" ", strip=True).split()).lower()
                if wanted in text:
                    return urljoin(page.url, href)
        return None

    def _next_page_url(self, page: engine.Page, next_no: int) -> str | None:
        """GePNIC pagination: numbered anchors whose href targets linkPage."""
        doc = page.select()
        for a in doc.css("a"):
            href = a.attrib.get("href")
            if not href or "linkpage" not in href.lower():
                continue
            if a.get_all_text(strip=True).strip() == str(next_no):
                return urljoin(page.url, href)
        return None

    # --- parsing ---------------------------------------------------------------

    def _parse_nic_table(self, page: engine.Page, page_url: str) -> list[TenderRecord]:
        """Parse the GePNIC 'Latest Active Tenders' list.

        Columns: S.No | e-Published Date | Closing Date | Opening Date |
                 Title and Ref.No./Tender ID | Organisation Chain

        The canonical table (#table / .list_table) is tried first; if it's
        missing or empty, every table on the page is scanned and the one
        yielding the most tender-shaped rows wins (GePNIC instances vary
        their markup).
        """
        doc = page.select()
        preferred = doc.css("table#table").first or doc.css("table.list_table").first
        if preferred is not None:
            records = self._parse_rows(preferred, page_url)
            if records:
                return records
        best: list[TenderRecord] = []
        for table in doc.css("table"):
            records = self._parse_rows(table, page_url)
            if len(records) > len(best):
                best = records
        return best

    def _parse_rows(self, table, page_url: str) -> list[TenderRecord]:
        records: list[TenderRecord] = []
        for row in table.css("tr"):
            cells = row.css("td")
            if len(cells) < 6:
                continue
            # collapse interior newlines/whitespace runs inside each cell
            texts = [" ".join(c.get_all_text(" ", strip=True).split()) for c in cells]
            if not texts[0].rstrip(".").isdigit():
                continue  # header / pagination rows
            published = self.parse_date(texts[1])
            closing = self.parse_dt(texts[2])
            if published is None and closing is None:
                continue  # 6-cell row that isn't a tender row
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
            if href:
                href = urljoin(page_url, href)
            records.append(TenderRecord(
                tender_ref_no=(ref_no or title)[:160],
                title=title or title_text,
                organisation=texts[5][:300] or None,
                published_date=published,
                closing_date=closing,
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
