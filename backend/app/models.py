"""SQLAlchemy ORM models. All timestamps are stored in UTC (naive);
the frontend renders them in IST (Asia/Kolkata)."""
from datetime import datetime, date

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.utcnow()


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    company_name: Mapped[str | None] = mapped_column(String(255))
    gstin: Mapped[str | None] = mapped_column(String(15))
    industry: Mapped[str | None] = mapped_column(String(120))
    state: Mapped[str | None] = mapped_column(String(80))
    tier: Mapped[str] = mapped_column(String(20), default="free")  # free | pro
    role: Mapped[str] = mapped_column(String(20), default="user")  # user | superadmin
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Notification preferences
    digest_hour_ist: Mapped[int] = mapped_column(Integer, default=7)   # 0-23, IST
    instant_alerts_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    weekly_report_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    whatsapp_number: Mapped[str | None] = mapped_column(String(20))    # stub channel

    # Email verification / password reset
    verification_token: Mapped[str | None] = mapped_column(String(64), index=True)
    reset_otp: Mapped[str | None] = mapped_column(String(6))
    reset_otp_expires: Mapped[datetime | None] = mapped_column(DateTime)

    last_login_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_digest_sent_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    keywords: Mapped[list["Keyword"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Keyword(Base):
    __tablename__ = "keywords"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    keyword_text: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(20), default="primary")  # primary | secondary
    synonyms_json: Mapped[list] = mapped_column(JSON, default=list)       # ["RPAS", "drone"]
    boolean_operator: Mapped[str] = mapped_column(String(8), default="OR")  # joins terms inside keyword_text
    portals_json: Mapped[list] = mapped_column(JSON, default=list)        # portal codes to search; [] = all allowed
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    user: Mapped[User] = relationship(back_populates="keywords")


class PortalSource(Base):
    __tablename__ = "portal_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)  # e.g. "cppp"
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    scraper_type: Mapped[str] = mapped_column(String(20), default="firecrawl")  # firecrawl | playwright | stub
    portal_group: Mapped[str] = mapped_column(String(20), default="central")    # central | state
    state: Mapped[str | None] = mapped_column(String(80))
    tier_required: Mapped[str] = mapped_column(String(20), default="pro")       # free | pro
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_scraped_at: Mapped[datetime | None] = mapped_column(DateTime)
    scrape_interval_hours: Mapped[int] = mapped_column(Integer, default=6)
    notes: Mapped[str | None] = mapped_column(String(255))


class Tender(Base):
    __tablename__ = "tenders"
    __table_args__ = (
        UniqueConstraint("portal_source_id", "tender_ref_no", name="uq_tender_portal_ref"),
        Index("ix_tenders_closing_date", "closing_date"),
        Index("ix_tenders_scraped_at", "scraped_at"),
        Index("ix_tenders_state", "state"),
        Index("ix_tenders_category", "category"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    portal_source_id: Mapped[int] = mapped_column(ForeignKey("portal_sources.id"), index=True)
    tender_ref_no: Mapped[str] = mapped_column(String(160), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    organisation: Mapped[str | None] = mapped_column(String(300))
    department: Mapped[str | None] = mapped_column(String(300))
    category: Mapped[str | None] = mapped_column(String(40))  # works | goods | services
    state: Mapped[str | None] = mapped_column(String(80))
    published_date: Mapped[date | None] = mapped_column(Date)
    closing_date: Mapped[datetime | None] = mapped_column(DateTime)
    estimated_value: Mapped[float | None] = mapped_column(Numeric(18, 2))
    document_url: Mapped[str | None] = mapped_column(String(1000))
    raw_url: Mapped[str | None] = mapped_column(String(1000))
    description_text: Mapped[str | None] = mapped_column(Text)
    raw_html_path: Mapped[str | None] = mapped_column(String(500))  # object-storage key for audit
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    scraped_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    portal: Mapped[PortalSource] = relationship()


class TenderArchive(Base):
    """Tenders older than ARCHIVE_AFTER_DAYS are moved here by the archiver job."""

    __tablename__ = "tenders_archive"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    original_tender_id: Mapped[int] = mapped_column(Integer, index=True)
    portal_source_id: Mapped[int] = mapped_column(Integer)
    tender_ref_no: Mapped[str] = mapped_column(String(160))
    title: Mapped[str] = mapped_column(Text)
    organisation: Mapped[str | None] = mapped_column(String(300))
    department: Mapped[str | None] = mapped_column(String(300))
    category: Mapped[str | None] = mapped_column(String(40))
    state: Mapped[str | None] = mapped_column(String(80))
    published_date: Mapped[date | None] = mapped_column(Date)
    closing_date: Mapped[datetime | None] = mapped_column(DateTime)
    estimated_value: Mapped[float | None] = mapped_column(Numeric(18, 2))
    document_url: Mapped[str | None] = mapped_column(String(1000))
    raw_url: Mapped[str | None] = mapped_column(String(1000))
    description_text: Mapped[str | None] = mapped_column(Text)
    archived_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class TenderKeywordMatch(Base):
    __tablename__ = "tender_keyword_matches"
    __table_args__ = (
        UniqueConstraint("tender_id", "keyword_id", name="uq_match_tender_keyword"),
        Index("ix_matches_user_score", "user_id", "relevance_score"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tender_id: Mapped[int] = mapped_column(ForeignKey("tenders.id", ondelete="CASCADE"), index=True)
    keyword_id: Mapped[int] = mapped_column(ForeignKey("keywords.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    relevance_score: Mapped[float] = mapped_column(Float, default=0)
    match_details_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    tender: Mapped[Tender] = relationship()
    keyword: Mapped[Keyword] = relationship()


class UserTenderStatus(Base):
    __tablename__ = "user_tender_status"
    __table_args__ = (
        UniqueConstraint("user_id", "tender_id", name="uq_user_tender"),
    )

    STATUSES = ("none", "interested", "bidding", "won", "lost", "ignored")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    tender_id: Mapped[int] = mapped_column(ForeignKey("tenders.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="none")
    notes: Mapped[str | None] = mapped_column(Text)
    bookmarked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    tender: Mapped[Tender] = relationship()


class ScrapeLog(Base):
    __tablename__ = "scrape_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    portal_source_id: Mapped[int] = mapped_column(ForeignKey("portal_sources.id"), index=True)
    run_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    status: Mapped[str] = mapped_column(String(20), default="running")  # running|success|partial|failed|skipped
    records_found: Mapped[int] = mapped_column(Integer, default=0)
    records_new: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    triggered_by: Mapped[str] = mapped_column(String(40), default="scheduler")  # scheduler|manual|api

    portal: Mapped[PortalSource] = relationship()


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    report_type: Mapped[str] = mapped_column(String(30))  # daily | weekly | custom
    file_format: Mapped[str] = mapped_column(String(10), default="pdf")  # pdf | csv | xlsx
    date_range_start: Mapped[date | None] = mapped_column(Date)
    date_range_end: Mapped[date | None] = mapped_column(Date)
    filters_json: Mapped[dict] = mapped_column(JSON, default=dict)
    file_path: Mapped[str | None] = mapped_column(String(500))
    tender_count: Mapped[int] = mapped_column(Integer, default=0)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(20), default="instant")  # digest | instant | system
    title: Mapped[str] = mapped_column(String(300))
    body: Mapped[str | None] = mapped_column(Text)
    tender_ids_json: Mapped[list] = mapped_column(JSON, default=list)
    channel: Mapped[str] = mapped_column(String(20), default="email")  # email | whatsapp(stub) | inapp
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending | sent | failed
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class KeywordBlacklist(Base):
    __tablename__ = "keyword_blacklist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    term: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
