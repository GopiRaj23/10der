from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..config import settings
from ..database import get_db
from ..models import Keyword, KeywordBlacklist, PortalSource, User
from ..schemas import KeywordIn, KeywordOut

router = APIRouter(prefix="/keywords", tags=["keywords"])


def _check_blacklist(db: Session, payload: KeywordIn) -> None:
    terms = {payload.keyword_text.lower(), *(s.lower() for s in payload.synonyms)}
    blacklisted = db.scalars(select(KeywordBlacklist.term)).all()
    hits = [b for b in blacklisted if b.lower() in terms]
    if hits:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            f"Keyword blocked by admin policy: {', '.join(hits)}")


def _check_portals(db: Session, user: User, codes: list[str]) -> None:
    if not codes:
        return
    portals = {p.code: p for p in db.scalars(select(PortalSource)).all()}
    unknown = [c for c in codes if c not in portals]
    if unknown:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            f"Unknown portal codes: {', '.join(unknown)}")
    if user.tier == "free":
        locked = [c for c in codes if portals[c].tier_required != "free"]
        if locked:
            raise HTTPException(
                status.HTTP_402_PAYMENT_REQUIRED,
                f"Portals {', '.join(locked)} require the Pro plan. Upgrade to access "
                f"all {len(portals)} portals.",
            )


@router.get("", response_model=list[KeywordOut])
def list_keywords(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(
        select(Keyword).where(Keyword.user_id == user.id).order_by(Keyword.created_at)
    ).all()


@router.post("", response_model=KeywordOut, status_code=status.HTTP_201_CREATED)
def create_keyword(payload: KeywordIn, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    count = db.scalar(select(func.count(Keyword.id)).where(Keyword.user_id == user.id))
    if user.tier == "free" and count >= settings.free_tier_keyword_limit:
        raise HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED,
            f"Free plan allows {settings.free_tier_keyword_limit} keywords. "
            "Upgrade to Pro for unlimited keywords.",
        )
    _check_blacklist(db, payload)
    _check_portals(db, user, payload.portals)

    keyword = Keyword(
        user_id=user.id,
        keyword_text=payload.keyword_text,
        category=payload.category,
        synonyms_json=payload.synonyms,
        boolean_operator=payload.boolean_operator,
        portals_json=payload.portals,
        is_active=payload.is_active,
    )
    db.add(keyword)
    db.commit()
    db.refresh(keyword)
    return keyword


@router.put("/{keyword_id}", response_model=KeywordOut)
def update_keyword(keyword_id: int, payload: KeywordIn,
                   user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    keyword = db.get(Keyword, keyword_id)
    if not keyword or keyword.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Keyword not found")
    _check_blacklist(db, payload)
    _check_portals(db, user, payload.portals)
    keyword.keyword_text = payload.keyword_text
    keyword.category = payload.category
    keyword.synonyms_json = payload.synonyms
    keyword.boolean_operator = payload.boolean_operator
    keyword.portals_json = payload.portals
    keyword.is_active = payload.is_active
    db.commit()
    db.refresh(keyword)
    return keyword


@router.delete("/{keyword_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_keyword(keyword_id: int, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    keyword = db.get(Keyword, keyword_id)
    if not keyword or keyword.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Keyword not found")
    db.delete(keyword)
    db.commit()
