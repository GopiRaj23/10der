"""Maps portal codes to scraper classes. DEMO_MODE swaps every scraper for the
sample-data generator so the product can be evaluated without live access."""
from ..config import settings
from .base import BaseScraper
from .cppp import CPPPScraper
from .demo import DemoScraper
from .gem import GeMScraper
from .stubs import (
    AndhraPradeshScraper,
    BHELScraper,
    DelhiScraper,
    DefenceProcScraper,
    DRDOScraper,
    EtendersNICScraper,
    GujaratScraper,
    HALScraper,
    IREPSScraper,
    KarnatakaScraper,
    KeralaScraper,
    MaharashtraScraper,
    ONGCScraper,
    RajasthanScraper,
    TamilNaduScraper,
    TelanganaScraper,
    UttarPradeshScraper,
)

SCRAPERS: dict[str, type[BaseScraper]] = {
    # Central
    "gem": GeMScraper,
    "cppp": CPPPScraper,
    "etenders-nic": EtendersNICScraper,
    "defproc": DefenceProcScraper,
    "drdo": DRDOScraper,
    "ireps": IREPSScraper,
    "bhel": BHELScraper,
    "ongc": ONGCScraper,
    "hal": HALScraper,
    # State
    "tn": TamilNaduScraper,
    "ka": KarnatakaScraper,
    "ap": AndhraPradeshScraper,
    "tg": TelanganaScraper,
    "mh": MaharashtraScraper,
    "gj": GujaratScraper,
    "up": UttarPradeshScraper,
    "dl": DelhiScraper,
    "kl": KeralaScraper,
    "rj": RajasthanScraper,
}


def get_scraper(portal) -> BaseScraper:
    if settings.demo_mode:
        return DemoScraper(portal)
    cls = SCRAPERS.get(portal.code)
    if cls is None:
        from .stubs import _StubScraper
        return _StubScraper(portal)
    return cls(portal)
