"""Seed script: portal sources (all 19 portals), superadmin, a demo user with
sample keywords, and (optionally) demo tender data.

Usage:
    python -m app.seed              # portals + users + keywords
    python -m app.seed --scrape     # …then run a scrape (demo data in DEMO_MODE)
"""
import logging
import sys

from sqlalchemy import select

from .auth import hash_password
from .config import settings
from .database import SessionLocal, init_db
from .models import Keyword, PortalSource, User

logger = logging.getLogger("tenderradar.seed")

# code, name, base_url, scraper_type, group, state, tier, notes
PORTALS = [
    # --- Central government ---
    ("gem", "GeM (Government e-Marketplace)", "https://bidplus.gem.gov.in",
     "playwright", "central", None, "free", "Bids + products + services"),
    ("cppp", "CPPP (Central Public Procurement Portal)", "https://eprocure.gov.in",
     "firecrawl", "central", None, "free", "NIC-hosted, main central portal"),
    ("etenders-nic", "eProcurement NIC (etenders.gov.in)", "https://etenders.gov.in",
     "firecrawl", "central", None, "free", "Works & services tenders"),
    ("defproc", "Defence eProcurement (MoD)", "https://defproc.gov.in",
     "firecrawl", "central", None, "pro", "Ministry of Defence tenders"),
    ("drdo", "DRDO eTender", "https://www.drdo.gov.in",
     "stub", "central", None, "pro", "R&D and supply tenders"),
    ("ireps", "IREPS (Indian Railways)", "https://www.ireps.gov.in",
     "playwright", "central", None, "pro", "Railway tenders"),
    ("bhel", "BHEL eProcurement", "https://www.bhel.com/eprocurement",
     "stub", "central", None, "pro", "PSU — power & industrial"),
    ("ongc", "ONGC eTender", "https://etender.ongc.co.in",
     "stub", "central", None, "pro", "PSU — oil & gas"),
    ("hal", "HAL eProcurement", "https://hal-india.co.in",
     "stub", "central", None, "pro", "Hindustan Aeronautics Ltd"),
    # --- State government ---
    ("tn", "Tamil Nadu eTenders", "https://tntenders.gov.in",
     "firecrawl", "state", "Tamil Nadu", "pro", "GePNIC instance"),
    ("ka", "Karnataka eProcurement", "https://eproc.karnataka.gov.in",
     "stub", "state", "Karnataka", "pro", "Custom platform"),
    ("ap", "Andhra Pradesh eProcurement", "https://eprocure.ap.gov.in",
     "firecrawl", "state", "Andhra Pradesh", "pro", "GePNIC instance"),
    ("tg", "Telangana eProcurement", "https://tender.telangana.gov.in",
     "stub", "state", "Telangana", "pro", "Custom platform"),
    ("mh", "Maharashtra eTenders", "https://mahatenders.gov.in",
     "firecrawl", "state", "Maharashtra", "pro", "GePNIC instance"),
    ("gj", "Gujarat nProcure", "https://www.nprocure.com",
     "stub", "state", "Gujarat", "pro", "(n)Code platform"),
    ("up", "Uttar Pradesh eTender", "https://etender.up.nic.in",
     "firecrawl", "state", "Uttar Pradesh", "pro", "GePNIC instance"),
    ("dl", "Delhi Govt Procurement", "https://govtprocurement.delhi.gov.in",
     "firecrawl", "state", "Delhi", "pro", "GePNIC instance"),
    ("kl", "Kerala eTenders", "https://etenders.kerala.gov.in",
     "firecrawl", "state", "Kerala", "pro", "GePNIC instance"),
    ("rj", "Rajasthan SPPP", "https://sppp.rajasthan.gov.in",
     "stub", "state", "Rajasthan", "pro", "SPPP portal"),
]

DEMO_KEYWORDS = [
    ("UAV", "primary", ["unmanned aerial vehicle", "RPAS", "drone"], "OR"),
    ("surveillance AND camera", "primary", ["CCTV"], "AND"),
    ("thermal camera", "primary", ["thermal imaging", "EO/IR"], "OR"),
    ("composite materials", "secondary", ["carbon fibre", "carbon fiber"], "OR"),
    ("radar NOT doppler", "secondary", ["electronic warfare"], "OR"),
    ("drone survey", "secondary", ["photogrammetry", "LiDAR"], "OR"),
]


def seed_portals(db) -> int:
    created = 0
    for code, name, url, scraper_type, group, state, tier, notes in PORTALS:
        existing = db.scalar(select(PortalSource).where(PortalSource.code == code))
        if existing:
            continue
        db.add(PortalSource(
            code=code, name=name, base_url=url, scraper_type=scraper_type,
            portal_group=group, state=state, tier_required=tier,
            scrape_interval_hours=settings.scrape_interval_hours, notes=notes,
        ))
        created += 1
    db.commit()
    return created


def seed_users(db) -> None:
    if not db.scalar(select(User).where(User.email == settings.admin_email)):
        db.add(User(
            email=settings.admin_email,
            password_hash=hash_password(settings.admin_password),
            company_name="TenderRadar Admin",
            role="superadmin", tier="pro", is_verified=True,
        ))
        logger.info("Created superadmin %s", settings.admin_email)

    demo_email = "demo@tenderradar.example"
    demo = db.scalar(select(User).where(User.email == demo_email))
    if not demo:
        demo = User(
            email=demo_email,
            password_hash=hash_password("Demo@12345"),
            company_name="AeroVision Systems Pvt Ltd",
            industry="Defence & Aerospace",
            state="Tamil Nadu",
            gstin="33AABCA1234F1Z5",
            tier="pro", is_verified=True,
        )
        db.add(demo)
        db.flush()
        for text, category, synonyms, op in DEMO_KEYWORDS:
            db.add(Keyword(user_id=demo.id, keyword_text=text, category=category,
                           synonyms_json=synonyms, boolean_operator=op))
        logger.info("Created demo user %s with %d keywords", demo_email, len(DEMO_KEYWORDS))

    free_email = "free@tenderradar.example"
    if not db.scalar(select(User).where(User.email == free_email)):
        free_user = User(
            email=free_email,
            password_hash=hash_password("Free@12345"),
            company_name="Sunrise Traders",
            industry="Office Supplies",
            state="Maharashtra",
            tier="free", is_verified=True,
        )
        db.add(free_user)
        db.flush()
        db.add(Keyword(user_id=free_user.id, keyword_text="furniture",
                       category="primary", synonyms_json=["workstation"]))
        db.add(Keyword(user_id=free_user.id, keyword_text="solar",
                       category="secondary", synonyms_json=["photovoltaic"]))
        logger.info("Created free-tier user %s", free_email)
    db.commit()


def main() -> None:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s — %(message)s")
    init_db()
    db = SessionLocal()
    try:
        created = seed_portals(db)
        logger.info("Portal sources: %d created (%d total)", created,
                    len(db.scalars(select(PortalSource)).all()))
        seed_users(db)

        if "--scrape" in sys.argv:
            from .services.scrape_service import run_all_portals

            logger.info("Running initial scrape (DEMO_MODE=%s)…", settings.demo_mode)
            logs = run_all_portals(db, triggered_by="seed")
            ok = sum(1 for l in logs if l.status == "success")
            logger.info("Scrape finished: %d/%d portals succeeded", ok, len(logs))
    finally:
        db.close()


if __name__ == "__main__":
    main()
