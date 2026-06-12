"""Tender search/listing, detail, status & watchlist, related, AI summary and
share links. Full-text search uses PostgreSQL tsvector (ILIKE on SQLite)."""
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.orm import Session

from ..auth import create_share_token, get_current_user
from ..config import settings
from ..database import get_db, is_postgres
from ..models import (
    PortalSource,
    Tender,
    TenderKeywordMatch,
    User,
    UserTenderStatus,
)
from ..schemas import (
    AISummaryOut,
    ShareLinkOut,
    TenderDetailOut,
    TenderListOut,
    TenderOut,
    TenderStatusUpdate,
)
from ..services.ai_summary import summarize_tender
from ..utils.timeutil import fmt_ist, utcnow

router = APIRouter(prefix="/tenders", tags=["tenders"])
share_router = APIRouter(prefix="/share", tags=["tenders"])


def _tender_out(tender: Tender, portal: PortalSource | None, score,
                status_row: UserTenderStatus | None) -> TenderOut:
    return TenderOut(
        id=tender.id,
        tender_ref_no=tender.tender_ref_no,
        title=tender.title,
        organisation=tender.organisation,
        department=tender.department,
        category=tender.category,
        state=tender.state,
        published_date=tender.published_date,
        closing_date=tender.closing_date,
        estimated_value=float(tender.estimated_value) if tender.estimated_value is not None else None,
        document_url=tender.document_url,
        raw_url=tender.raw_url,
        scraped_at=tender.scraped_at,
        portal_code=portal.code if portal else None,
        portal_name=portal.name if portal else None,
        relevance_score=float(score) if score is not None else None,
        user_status=status_row.status if status_row else None,
        bookmarked=bool(status_row.bookmarked) if status_row else False,
    )


def _base_query(user: User):
    best_score = (
        select(
            TenderKeywordMatch.tender_id.label("tender_id"),
            func.max(TenderKeywordMatch.relevance_score).label("score"),
        )
        .where(TenderKeywordMatch.user_id == user.id)
        .group_by(TenderKeywordMatch.tender_id)
        .subquery()
    )
    stmt = (
        select(Tender, PortalSource, best_score.c.score, UserTenderStatus)
        .join(PortalSource, Tender.portal_source_id == PortalSource.id)
        .outerjoin(best_score, best_score.c.tender_id == Tender.id)
        .outerjoin(
            UserTenderStatus,
            and_(UserTenderStatus.tender_id == Tender.id,
                 UserTenderStatus.user_id == user.id),
        )
        .where(Tender.is_archived.is_(False))
    )
    if user.tier == "free":
        stmt = stmt.where(PortalSource.tier_required == "free")
    return stmt, best_score


@router.get("", response_model=TenderListOut)
def list_tenders(
    keyword: str | None = Query(default=None, max_length=200),
    portal: str | None = None,
    state: str | None = None,
    category: str | None = None,
    organisation: str | None = Query(default=None, max_length=200),
    closing_before: date | None = None,
    closing_within_days: int | None = Query(default=None, ge=1, le=365),
    published_from: date | None = None,
    published_to: date | None = None,
    value_min: float | None = Query(default=None, ge=0),
    value_max: float | None = Query(default=None, ge=0),
    min_score: float | None = Query(default=None, ge=0, le=100),
    mine: bool = False,
    status_filter: str | None = Query(default=None, alias="status"),
    sort: str = Query(default="relevance", pattern="^(relevance|closing|published)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt, best_score = _base_query(user)

    if keyword:
        if is_postgres():
            stmt = stmt.where(
                text("tenders.search_vector @@ plainto_tsquery('english', :fts_q)")
                .bindparams(fts_q=keyword)
            )
        else:
            like = f"%{keyword}%"
            stmt = stmt.where(or_(
                Tender.title.ilike(like),
                Tender.description_text.ilike(like),
                Tender.organisation.ilike(like),
            ))
    if portal:
        stmt = stmt.where(PortalSource.code == portal)
    if state:
        stmt = stmt.where(Tender.state == state)
    if category:
        stmt = stmt.where(Tender.category == category)
    if organisation:
        stmt = stmt.where(Tender.organisation.ilike(f"%{organisation}%"))
    if closing_before:
        stmt = stmt.where(Tender.closing_date <= datetime.combine(closing_before, datetime.max.time()))
    if closing_within_days:
        stmt = stmt.where(
            Tender.closing_date.isnot(None),
            Tender.closing_date >= utcnow(),
            Tender.closing_date <= utcnow() + timedelta(days=closing_within_days),
        )
    if published_from:
        stmt = stmt.where(Tender.published_date >= published_from)
    if published_to:
        stmt = stmt.where(Tender.published_date <= published_to)
    if value_min is not None:
        stmt = stmt.where(Tender.estimated_value >= value_min)
    if value_max is not None:
        stmt = stmt.where(Tender.estimated_value <= value_max)
    if min_score is not None:
        stmt = stmt.where(best_score.c.score >= min_score)
    if mine:
        stmt = stmt.where(best_score.c.score.isnot(None))
    if status_filter:
        stmt = stmt.where(UserTenderStatus.status == status_filter)

    if sort == "relevance":
        stmt = stmt.order_by(func.coalesce(best_score.c.score, 0).desc(),
                             Tender.scraped_at.desc())
    elif sort == "closing":
        stmt = stmt.order_by(Tender.closing_date.asc().nullslast())
    else:  # published
        stmt = stmt.order_by(Tender.published_date.desc().nullslast())

    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    rows = db.execute(stmt.offset((page - 1) * page_size).limit(page_size)).all()

    return TenderListOut(
        items=[_tender_out(t, p, s, st) for t, p, s, st in rows],
        total=total, page=page, page_size=page_size,
    )


@router.get("/bookmarks", response_model=list[TenderOut])
def bookmarks(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    stmt, _ = _base_query(user)
    stmt = stmt.where(UserTenderStatus.bookmarked.is_(True)).order_by(
        Tender.closing_date.asc().nullslast())
    rows = db.execute(stmt).all()
    return [_tender_out(t, p, s, st) for t, p, s, st in rows]


@router.get("/{tender_id}", response_model=TenderDetailOut)
def tender_detail(tender_id: int, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    stmt, _ = _base_query(user)
    row = db.execute(stmt.where(Tender.id == tender_id)).first()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tender not found")
    tender, portal, score, status_row = row
    base = _tender_out(tender, portal, score, status_row)
    matched = db.scalars(
        select(TenderKeywordMatch)
        .where(TenderKeywordMatch.tender_id == tender_id,
               TenderKeywordMatch.user_id == user.id)
    ).all()
    return TenderDetailOut(
        **base.model_dump(),
        description_text=tender.description_text,
        notes=status_row.notes if status_row else None,
        matched_keywords=[(m.match_details_json or {}).get("keyword", "") for m in matched],
    )


@router.get("/{tender_id}/related", response_model=list[TenderOut])
def related_tenders(tender_id: int, user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    tender = db.get(Tender, tender_id)
    if not tender:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tender not found")
    stmt, _ = _base_query(user)
    conditions = []
    if tender.organisation:
        conditions.append(Tender.organisation == tender.organisation)
    if tender.category:
        conditions.append(Tender.category == tender.category)
    stmt = (stmt.where(Tender.id != tender_id, or_(*conditions) if conditions else text("1=1"))
            .order_by(Tender.closing_date.asc().nullslast()).limit(5))
    rows = db.execute(stmt).all()
    return [_tender_out(t, p, s, st) for t, p, s, st in rows]


@router.post("/{tender_id}/status", response_model=TenderOut)
def update_status(tender_id: int, payload: TenderStatusUpdate,
                  user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    tender = db.get(Tender, tender_id)
    if not tender or tender.is_archived:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tender not found")
    status_row = db.scalar(
        select(UserTenderStatus).where(UserTenderStatus.user_id == user.id,
                                       UserTenderStatus.tender_id == tender_id))
    if not status_row:
        status_row = UserTenderStatus(user_id=user.id, tender_id=tender_id)
        db.add(status_row)
    if payload.status is not None:
        status_row.status = payload.status
    if payload.bookmarked is not None:
        status_row.bookmarked = payload.bookmarked
    if payload.notes is not None:
        status_row.notes = payload.notes
    db.commit()

    stmt, _ = _base_query(user)
    tender_obj, portal, score, st = db.execute(stmt.where(Tender.id == tender_id)).first()
    return _tender_out(tender_obj, portal, score, st)


@router.get("/{tender_id}/summary", response_model=AISummaryOut)
def ai_summary(tender_id: int, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    tender = db.get(Tender, tender_id)
    if not tender:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tender not found")
    provider, bullets = summarize_tender(
        tender.title, tender.description_text, tender.organisation,
        fmt_ist(tender.closing_date),
        f"₹{float(tender.estimated_value):,.0f}" if tender.estimated_value else None,
    )
    return AISummaryOut(provider=provider, summary=bullets)


@router.post("/{tender_id}/share", response_model=ShareLinkOut)
def create_share_link(tender_id: int, user: User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    tender = db.get(Tender, tender_id)
    if not tender:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tender not found")
    token = create_share_token(tender_id)
    return ShareLinkOut(
        share_token=token,
        share_url=f"{settings.frontend_origin}/share/{token}",
        expires_in_days=30,
    )


@share_router.get("/{token}", response_model=TenderOut)
def view_shared(token: str, db: Session = Depends(get_db)):
    """Read-only shared tender view (no auth — link is the credential)."""
    from ..auth import decode_token
    payload = decode_token(token, "share")
    tender = db.get(Tender, int(payload["tender_id"]))
    if not tender:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tender not found")
    portal = db.get(PortalSource, tender.portal_source_id)
    return _tender_out(tender, portal, None, None)
