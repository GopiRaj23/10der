"""Portal scrapers.

NIC/GePNIC-based portals reuse the working `NICGenericScraper` parse core
(they run the same software as CPPP, only the hostname/app-path differs).
Portals with custom platforms are stubs that share the same interface —
implement `scrape()` to bring them online; failures/skips are logged and
never crash the pipeline.
"""
from .base import BaseScraper, PlaywrightScraper, ScraperNotImplemented, TenderRecord
from .cppp import NICGenericScraper


# --- NIC/GePNIC family (working parse core, reused from CPPP) ---------------

class EtendersNICScraper(NICGenericScraper):
    """etenders.gov.in — central works & services."""
    portal_code = "etenders-nic"
    app_path = "/eprocure/app"


class DefenceProcScraper(NICGenericScraper):
    """defproc.gov.in — Ministry of Defence (GePNIC instance)."""
    portal_code = "defproc"
    app_path = "/nicgep/app"


class TamilNaduScraper(NICGenericScraper):
    portal_code = "tn"
    app_path = "/nicgep/app"


class AndhraPradeshScraper(NICGenericScraper):
    portal_code = "ap"
    app_path = "/nicgep/app"


class MaharashtraScraper(NICGenericScraper):
    portal_code = "mh"
    app_path = "/nicgep/app"


class UttarPradeshScraper(NICGenericScraper):
    portal_code = "up"
    app_path = "/nicgep/app"


class DelhiScraper(NICGenericScraper):
    portal_code = "dl"
    app_path = "/nicgep/app"


class KeralaScraper(NICGenericScraper):
    portal_code = "kl"
    app_path = "/nicgep/app"


# --- Custom-platform portals (stubs with the standard interface) -------------

class _StubScraper(BaseScraper):
    portal_code = "stub"

    def scrape(self, search_terms: list[str]) -> list[TenderRecord]:
        raise ScraperNotImplemented(
            f"{self.portal_code}: scraper not yet implemented for "
            f"{self.base_url} — runs are skipped, not failed"
        )


class DRDOScraper(_StubScraper):
    """drdo.gov.in — R&D and supply tenders (custom CMS)."""
    portal_code = "drdo"


class IREPSScraper(PlaywrightScraper):
    """ireps.gov.in — Indian Railways (JSF app, needs session handling)."""
    portal_code = "ireps"

    def scrape(self, search_terms: list[str]) -> list[TenderRecord]:
        raise ScraperNotImplemented(
            "ireps: JSF-based portal requires session/viewstate handling — "
            "Playwright skeleton in place, parser not yet implemented"
        )


class BHELScraper(_StubScraper):
    """bhel.com/eprocurement — PSU portal."""
    portal_code = "bhel"


class ONGCScraper(_StubScraper):
    """ongctender.com — SAP SRM based."""
    portal_code = "ongc"


class HALScraper(_StubScraper):
    """hal-india.co.in — Hindustan Aeronautics."""
    portal_code = "hal"


class KarnatakaScraper(_StubScraper):
    """eproc.karnataka.gov.in — custom e-procurement v2 platform."""
    portal_code = "ka"


class TelanganaScraper(_StubScraper):
    """tender.telangana.gov.in — custom platform."""
    portal_code = "tg"


class GujaratScraper(_StubScraper):
    """nprocure.com — (n)Code Solutions platform."""
    portal_code = "gj"


class RajasthanScraper(_StubScraper):
    """sppp.rajasthan.gov.in — SPPP portal."""
    portal_code = "rj"
