"""UTC <-> IST helpers. Storage is always UTC; display is IST (UTC+5:30)."""
from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30), name="IST")


def utcnow() -> datetime:
    return datetime.utcnow()


def to_ist(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(IST)


def ist_now() -> datetime:
    return datetime.now(IST)


def fmt_ist(dt: datetime | None, fmt: str = "%d %b %Y, %I:%M %p IST") -> str:
    ist = to_ist(dt)
    return ist.strftime(fmt) if ist else "—"
