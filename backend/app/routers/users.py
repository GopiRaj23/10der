from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import Notification, User
from ..schemas import NotificationOut, UserOut, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut)
def get_me(user: User = Depends(get_current_user)):
    return user


@router.put("/me", response_model=UserOut)
def update_me(payload: UserUpdate, user: User = Depends(get_current_user),
              db: Session = Depends(get_db)):
    for field_name, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, field_name, value)
    db.commit()
    db.refresh(user)
    return user


@router.get("/me/notifications", response_model=list[NotificationOut])
def my_notifications(unread_only: bool = False, limit: int = 30,
                     user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    stmt = (select(Notification)
            .where(Notification.user_id == user.id)
            .order_by(Notification.created_at.desc())
            .limit(min(limit, 100)))
    if unread_only:
        stmt = stmt.where(Notification.is_read.is_(False))
    return db.scalars(stmt).all()


@router.post("/me/notifications/read-all")
def mark_all_read(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.execute(update(Notification)
               .where(Notification.user_id == user.id, Notification.is_read.is_(False))
               .values(is_read=True))
    db.commit()
    return {"message": "All notifications marked read"}


@router.post("/me/notifications/{notification_id}/read")
def mark_read(notification_id: int, user: User = Depends(get_current_user),
              db: Session = Depends(get_db)):
    notif = db.get(Notification, notification_id)
    if not notif or notif.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notification not found")
    notif.is_read = True
    db.commit()
    return {"message": "Marked read"}
