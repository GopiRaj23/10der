"""Dashboard stats & analytics: counters, urgent strip, portal heatmap,
keyword performance, status funnel and the closing-date calendar."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import (
    Keyword,
    PortalSource,
    Tender,
    TenderKeywordMatch,
    User,
    UserTenderStatus,
)
from ..utils.timeutil import ist_now, utcnow

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _matched_count(db: Session, user: User, since: datetime | None) -> int:
    stmt = select(func.count(func.distinct(TenderKeywordMatch.tender_id))).where(
        TenderKeywordMatch.user_id == user.id)
    if since:
        stmt = stmt.where(TenderKeywordMatch.created_at >= since)
    return db.scalar(stmt) or 0


@router.get("/stats")
def stats(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    now = utcnow()
    # "today" means the IST calendar day; convert IST midnight to naive UTC
    ist_today_start = ist_now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_start_utc = ist_today_start.astimezone(timezone.utc).replace(tzinfo=None)

    counts = {
        "today": _matched_count(db, user, today_start_utc),
        "week": _matched_count(db, user, now - timedelta(days=7)),
        "month": _matched_count(db, user, now - timedelta(days=30)),
        "all_time": _matched_count(db, user, None),
    }
    new_since_login = _matched_count(db, user, user.last_login_at) if user.last_login_at else counts["all_time"]

    # Urgent: matched tenders closing in the next 7 days
    urgent_rows = db.execute(
        select(Tender, PortalSource.name,
               func.max(TenderKeywordMatch.relevance_score))
        .join(TenderKeywordMatch, TenderKeywordMatch.tender_id == Tender.id)
        .join(PortalSource, Tender.portal_source_id == PortalSource.id)
        .where(
            TenderKeywordMatch.user_id == user.id,
            Tender.is_archived.is_(False),
            Tender.closing_date.isnot(None),
            Tender.closing_date >= now,
            Tender.closing_date <= now + timedelta(days=7),
        )
        .group_by(Tender.id, PortalSource.name)
        .order_by(Tender.closing_date.asc())
        .limit(8)
    ).all()

    funnel_rows = db.execute(
        select(UserTenderStatus.status, func.count())
        .where(UserTenderStatus.user_id == user.id)
        .group_by(UserTenderStatus.status)
    ).all()
    funnel = {status: count for status, count in funnel_rows}

    bookmark_count = db.scalar(
        select(func.count()).select_from(UserTenderStatus)
        .where(UserTenderStatus.user_id == user.id,
               UserTenderStatus.bookmarked.is_(True))) or 0

    last_sync = db.scalar(select(func.max(PortalSource.last_scraped_at)))
    active_keywords = db.scalar(
        select(func.count()).select_from(Keyword)
        .where(Keyword.user_id == user.id, Keyword.is_active.is_(True))) or 0

    return {
        "found": counts,
        "new_since_last_login": new_since_login,
        "closing_soon_count": len(urgent_rows),
        "closing_soon": [
            {
                "id": t.id, "title": t.title, "organisation": t.organisation,
                "portal_name": portal_name, "closing_date": t.closing_date,
                "relevance_score": float(score or 0),
            }
            for t, portal_name, score in urgent_rows
        ],
        "funnel": {
            "interested": funnel.get("interested", 0),
            "bidding": funnel.get("bidding", 0),
            "won": funnel.get("won", 0),
            "lost": funnel.get("lost", 0),
            "ignored": funnel.get("ignored", 0),
        },
        "bookmarks": bookmark_count,
        "active_keywords": active_keywords,
        "last_sync": last_sync,
        "tier": user.tier,
    }


@router.get("/analytics")
def analytics(days: int = Query(default=14, ge=7, le=90),
              user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    since = utcnow() - timedelta(days=days)

    # Portal activity heatmap: matched tenders per portal per day
    rows = db.execute(
        select(PortalSource.name, func.date(TenderKeywordMatch.created_at), func.count())
        .select_from(TenderKeywordMatch)
        .join(Tender, TenderKeywordMatch.tender_id == Tender.id)
        .join(PortalSource, Tender.portal_source_id == PortalSource.id)
        .where(TenderKeywordMatch.user_id == user.id,
               TenderKeywordMatch.created_at >= since)
        .group_by(PortalSource.name, func.date(TenderKeywordMatch.created_at))
    ).all()
    heatmap: dict[str, dict[str, int]] = {}
    for portal_name, day, count in rows:
        heatmap.setdefault(portal_name, {})[str(day)] = count

    # Keyword performance
    kw_rows = db.execute(
        select(Keyword.keyword_text,
               func.count(TenderKeywordMatch.id),
               func.avg(TenderKeywordMatch.relevance_score))
        .join(TenderKeywordMatch, TenderKeywordMatch.keyword_id == Keyword.id)
        .where(Keyword.user_id == user.id)
        .group_by(Keyword.keyword_text)
        .order_by(func.count(TenderKeywordMatch.id).desc())
    ).all()

    # Daily trend of new matches
    trend_rows = db.execute(
        select(func.date(TenderKeywordMatch.created_at), func.count())
        .where(TenderKeywordMatch.user_id == user.id,
               TenderKeywordMatch.created_at >= since)
        .group_by(func.date(TenderKeywordMatch.created_at))
        .order_by(func.date(TenderKeywordMatch.created_at))
    ).all()

    return {
        "portal_heatmap": heatmap,
        "keyword_performance": [
            {"keyword": k, "matches": c, "avg_score": round(float(a or 0), 1)}
            for k, c, a in kw_rows
        ],
        "trend": [{"date": str(d), "count": c} for d, c in trend_rows],
    }


@router.get("/calendar")
def calendar(month: str = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
             user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Tenders (matched to the user) closing on each day of the given month."""
    ref = datetime.strptime(month, "%Y-%m") if month else ist_now().replace(tzinfo=None)
    month_start = ref.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    next_month = (month_start + timedelta(days=32)).replace(day=1)

    rows = db.execute(
        select(Tender, PortalSource.name, func.max(TenderKeywordMatch.relevance_score))
        .join(TenderKeywordMatch, TenderKeywordMatch.tender_id == Tender.id)
        .join(PortalSource, Tender.portal_source_id == PortalSource.id)
        .where(
            TenderKeywordMatch.user_id == user.id,
            Tender.is_archived.is_(False),
            Tender.closing_date >= month_start,
            Tender.closing_date < next_month,
        )
        .group_by(Tender.id, PortalSource.name)
        .order_by(Tender.closing_date.asc())
    ).all()

    days: dict[str, list] = {}
    for t, portal_name, score in rows:
        key = t.closing_date.strftime("%Y-%m-%d")
        days.setdefault(key, []).append({
            "id": t.id, "title": t.title, "portal_name": portal_name,
            "closing_date": t.closing_date, "relevance_score": float(score or 0),
        })
    return {"month": month_start.strftime("%Y-%m"), "days": days}
