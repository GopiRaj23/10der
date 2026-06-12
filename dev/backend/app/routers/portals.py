from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import PortalSource, ScrapeLog, User
from ..schemas import PortalOut, PortalStatusOut

router = APIRouter(prefix="/portals", tags=["portals"])


@router.get("", response_model=list[PortalOut])
def list_portals(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(select(PortalSource).order_by(PortalSource.portal_group,
                                                    PortalSource.name)).all()


@router.get("/status", response_model=list[PortalStatusOut])
def portal_status(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    portals = db.scalars(select(PortalSource).order_by(PortalSource.portal_group,
                                                       PortalSource.name)).all()
    out = []
    for portal in portals:
        last_log = db.scalar(
            select(ScrapeLog)
            .where(ScrapeLog.portal_source_id == portal.id)
            .order_by(ScrapeLog.run_at.desc())
            .limit(1)
        )
        item = PortalStatusOut.model_validate(portal)
        if last_log:
            item.last_status = last_log.status
            item.last_records_found = last_log.records_found
            item.last_records_new = last_log.records_new
            item.last_error = last_log.error_message
            item.last_duration_seconds = last_log.duration_seconds
        out.append(item)
    return out
