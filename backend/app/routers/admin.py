"""Superadmin endpoints: user management, scraper/portal config, keyword
blacklist, system health and usage analytics."""
import os
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from ..auth import require_admin
from ..config import settings
from ..database import engine, get_db, is_postgres
from ..models import (
    Keyword,
    KeywordBlacklist,
    PortalSource,
    ScrapeLog,
    Tender,
    User,
)
from ..schemas import AdminUserUpdate, BlacklistIn, UserOut
from ..services.cache import cache
from ..utils.timeutil import utcnow

router = APIRouter(prefix="/admin", tags=["admin"],
                   dependencies=[Depends(require_admin)])


# --- Users -------------------------------------------------------------------

@router.get("/users")
def list_users(q: str | None = None, page: int = Query(default=1, ge=1),
               db: Session = Depends(get_db)):
    stmt = select(User).order_by(User.created_at.desc())
    if q:
        stmt = stmt.where(User.email.ilike(f"%{q}%") | User.company_name.ilike(f"%{q}%"))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    users = db.scalars(stmt.offset((page - 1) * 20).limit(20)).all()
    kw_counts = dict(db.execute(
        select(Keyword.user_id, func.count()).group_by(Keyword.user_id)).all())
    return {
        "total": total,
        "page": page,
        "items": [
            {**UserOut.model_validate(u).model_dump(), "keyword_count": kw_counts.get(u.id, 0)}
            for u in users
        ],
    }


@router.put("/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, payload: AdminUserUpdate,
                admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if user.id == admin.id and payload.is_active is False:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot disable your own account")
    for field_name, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, field_name, value)
    db.commit()
    db.refresh(user)
    return user


# --- Portal / scraper config ---------------------------------------------------

@router.put("/portals/{portal_id}")
def update_portal(portal_id: int, is_active: bool | None = None,
                  scrape_interval_hours: int | None = Query(default=None, ge=1, le=168),
                  db: Session = Depends(get_db)):
    portal = db.get(PortalSource, portal_id)
    if not portal:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Portal not found")
    if is_active is not None:
        portal.is_active = is_active
    if scrape_interval_hours is not None:
        portal.scrape_interval_hours = scrape_interval_hours
    db.commit()
    return {"message": "Portal updated", "code": portal.code,
            "is_active": portal.is_active,
            "scrape_interval_hours": portal.scrape_interval_hours}


# --- Keyword blacklist ----------------------------------------------------------

@router.get("/blacklist")
def list_blacklist(db: Session = Depends(get_db)):
    rows = db.scalars(select(KeywordBlacklist).order_by(KeywordBlacklist.term)).all()
    return [{"id": r.id, "term": r.term, "reason": r.reason,
             "created_at": r.created_at} for r in rows]


@router.post("/blacklist", status_code=status.HTTP_201_CREATED)
def add_blacklist(payload: BlacklistIn, db: Session = Depends(get_db)):
    existing = db.scalar(select(KeywordBlacklist)
                         .where(func.lower(KeywordBlacklist.term) == payload.term.lower()))
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Term already blacklisted")
    row = KeywordBlacklist(term=payload.term, reason=payload.reason)
    db.add(row)
    db.commit()
    return {"id": row.id, "term": row.term}


@router.delete("/blacklist/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_blacklist(item_id: int, db: Session = Depends(get_db)):
    row = db.get(KeywordBlacklist, item_id)
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    db.delete(row)
    db.commit()


# --- System health & usage -------------------------------------------------------

@router.get("/system-health")
def system_health(db: Session = Depends(get_db)):
    if is_postgres():
        db_size = db.scalar(text("SELECT pg_size_pretty(pg_database_size(current_database()))"))
    else:
        db_file = engine.url.database
        size = os.path.getsize(db_file) if db_file and os.path.exists(db_file) else 0
        db_size = f"{size / 1024 / 1024:.1f} MB"

    week_ago = utcnow() - timedelta(days=7)
    portal_rows = db.scalars(select(PortalSource)).all()
    portal_health = []
    for portal in portal_rows:
        logs = db.scalars(
            select(ScrapeLog).where(ScrapeLog.portal_source_id == portal.id,
                                    ScrapeLog.run_at >= week_ago)).all()
        total = len(logs)
        failed = sum(1 for l in logs if l.status == "failed")
        portal_health.append({
            "code": portal.code, "name": portal.name, "is_active": portal.is_active,
            "last_scraped_at": portal.last_scraped_at,
            "runs_7d": total, "failed_7d": failed,
            "error_rate": round(failed / total * 100, 1) if total else 0.0,
        })

    return {
        "db_size": db_size,
        "db_dialect": engine.dialect.name,
        "cache_backend": cache.backend,
        "redis_queue_depth": cache.queue_depth(),
        "tenders_total": db.scalar(select(func.count()).select_from(Tender)) or 0,
        "users_total": db.scalar(select(func.count()).select_from(User)) or 0,
        "demo_mode": settings.demo_mode,
        "portals": portal_health,
    }


@router.get("/usage")
def usage_analytics(db: Session = Depends(get_db)):
    today = utcnow().date()
    dau = db.scalar(select(func.count()).select_from(User)
                    .where(func.date(User.last_login_at) == today)) or 0
    top_keywords = db.execute(
        select(func.lower(Keyword.keyword_text), func.count())
        .group_by(func.lower(Keyword.keyword_text))
        .order_by(func.count().desc()).limit(10)).all()
    active_portals = db.execute(
        select(PortalSource.name, func.count(Tender.id))
        .join(Tender, Tender.portal_source_id == PortalSource.id)
        .group_by(PortalSource.name)
        .order_by(func.count(Tender.id).desc()).limit(10)).all()
    tiers = dict(db.execute(select(User.tier, func.count()).group_by(User.tier)).all())
    return {
        "dau": dau,
        "top_keywords": [{"keyword": k, "users": c} for k, c in top_keywords],
        "most_active_portals": [{"portal": p, "tenders": c} for p, c in active_portals],
        "tiers": tiers,
    }
