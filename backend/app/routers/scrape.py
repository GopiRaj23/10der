"""Manual scrape triggering + scrape logs. Scrapes run as FastAPI background
tasks with their own DB session so requests return immediately."""
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import SessionLocal, get_db
from ..models import PortalSource, ScrapeLog, User
from ..schemas import ScrapeLogOut, ScrapeTriggerRequest

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/scrape", tags=["scrape"])


def _run_scrape_background(portal_id: int | None, triggered_by: str) -> None:
    from ..services import scrape_service

    db = SessionLocal()
    try:
        if portal_id is None:
            scrape_service.run_all_portals(db, triggered_by=triggered_by)
        else:
            portal = db.get(PortalSource, portal_id)
            if portal:
                scrape_service.run_portal_scrape(db, portal, triggered_by=triggered_by)
    except Exception:
        logger.exception("Background scrape crashed")
    finally:
        db.close()


@router.post("/trigger", status_code=status.HTTP_202_ACCEPTED)
def trigger_scrape(payload: ScrapeTriggerRequest, background: BackgroundTasks,
                   user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if payload.portal_code:
        portal = db.scalar(select(PortalSource).where(PortalSource.code == payload.portal_code))
        if not portal:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Portal not found")
        if not portal.is_active:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Portal is disabled")
        if user.tier == "free" and user.role != "superadmin" and portal.tier_required != "free":
            raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED,
                                "This portal requires the Pro plan")
        background.add_task(_run_scrape_background, portal.id,
                            f"manual:{user.email}")
        return {"message": f"Scrape queued for {portal.name}"}

    if user.role != "superadmin":
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "Only admins can trigger a full scrape of all portals")
    background.add_task(_run_scrape_background, None, f"manual:{user.email}")
    return {"message": "Scrape queued for all active portals"}


@router.get("/logs", response_model=list[ScrapeLogOut])
def scrape_logs(limit: int = Query(default=50, le=200),
                portal_code: str | None = None,
                user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    stmt = (select(ScrapeLog, PortalSource)
            .join(PortalSource, ScrapeLog.portal_source_id == PortalSource.id)
            .order_by(ScrapeLog.run_at.desc())
            .limit(limit))
    if portal_code:
        stmt = stmt.where(PortalSource.code == portal_code)
    rows = db.execute(stmt).all()
    out = []
    for log, portal in rows:
        item = ScrapeLogOut.model_validate(log)
        item.portal_code = portal.code
        item.portal_name = portal.name
        out.append(item)
    return out
