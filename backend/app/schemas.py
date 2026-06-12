"""Pydantic request/response schemas."""
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from .utils.sanitize import clean_text, validate_keyword


# --- Auth -------------------------------------------------------------------

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    company_name: str | None = Field(default=None, max_length=255)
    industry: str | None = Field(default=None, max_length=120)
    state: str | None = Field(default=None, max_length=80)
    gstin: str | None = Field(default=None, max_length=15)

    @field_validator("company_name", "industry", "state", "gstin")
    @classmethod
    def _clean(cls, v):
        return clean_text(v, 255)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    otp: str = Field(min_length=6, max_length=6)
    new_password: str = Field(min_length=8, max_length=128)


class VerifyEmailRequest(BaseModel):
    token: str


# --- Users ------------------------------------------------------------------

class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    company_name: str | None
    gstin: str | None
    industry: str | None
    state: str | None
    tier: str
    role: str
    is_verified: bool
    digest_hour_ist: int
    instant_alerts_enabled: bool
    weekly_report_enabled: bool
    whatsapp_number: str | None
    last_login_at: datetime | None
    created_at: datetime


class UserUpdate(BaseModel):
    company_name: str | None = None
    gstin: str | None = Field(default=None, max_length=15)
    industry: str | None = None
    state: str | None = None
    digest_hour_ist: int | None = Field(default=None, ge=0, le=23)
    instant_alerts_enabled: bool | None = None
    weekly_report_enabled: bool | None = None
    whatsapp_number: str | None = Field(default=None, max_length=20)

    @field_validator("company_name", "industry", "state", "gstin", "whatsapp_number")
    @classmethod
    def _clean(cls, v):
        return clean_text(v, 255)


# --- Keywords ----------------------------------------------------------------

class KeywordIn(BaseModel):
    keyword_text: str
    category: str = Field(default="primary", pattern="^(primary|secondary)$")
    synonyms: list[str] = Field(default_factory=list, max_length=20)
    boolean_operator: str = Field(default="OR", pattern="^(AND|OR|NOT)$")
    portals: list[str] = Field(default_factory=list, max_length=30)
    is_active: bool = True

    @field_validator("keyword_text")
    @classmethod
    def _validate_keyword(cls, v):
        return validate_keyword(v)

    @field_validator("synonyms")
    @classmethod
    def _validate_synonyms(cls, v):
        return [validate_keyword(s) for s in v if s and s.strip()]


class KeywordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    keyword_text: str
    category: str
    synonyms_json: list
    boolean_operator: str
    portals_json: list
    is_active: bool
    created_at: datetime


# --- Portals ------------------------------------------------------------------

class PortalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    base_url: str
    scraper_type: str
    portal_group: str
    state: str | None
    tier_required: str
    is_active: bool
    last_scraped_at: datetime | None
    scrape_interval_hours: int


class PortalStatusOut(PortalOut):
    last_status: str | None = None
    last_records_found: int | None = None
    last_records_new: int | None = None
    last_error: str | None = None
    last_duration_seconds: float | None = None


# --- Tenders -------------------------------------------------------------------

class TenderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tender_ref_no: str
    title: str
    organisation: str | None
    department: str | None
    category: str | None
    state: str | None
    published_date: date | None
    closing_date: datetime | None
    estimated_value: float | None
    document_url: str | None
    raw_url: str | None
    scraped_at: datetime

    # joined/computed
    portal_code: str | None = None
    portal_name: str | None = None
    relevance_score: float | None = None
    user_status: str | None = None
    bookmarked: bool = False


class TenderDetailOut(TenderOut):
    description_text: str | None = None
    notes: str | None = None
    matched_keywords: list[str] = Field(default_factory=list)


class TenderListOut(BaseModel):
    items: list[TenderOut]
    total: int
    page: int
    page_size: int


class TenderStatusUpdate(BaseModel):
    status: str | None = Field(default=None, pattern="^(none|interested|bidding|won|lost|ignored)$")
    bookmarked: bool | None = None
    notes: str | None = Field(default=None, max_length=4000)

    @field_validator("notes")
    @classmethod
    def _clean(cls, v):
        return clean_text(v, 4000)


class ShareLinkOut(BaseModel):
    share_token: str
    share_url: str
    expires_in_days: int


class AISummaryOut(BaseModel):
    provider: str
    summary: list[str]


# --- Scraping --------------------------------------------------------------------

class ScrapeTriggerRequest(BaseModel):
    portal_code: str | None = None  # None = all active portals


class ScrapeLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    portal_source_id: int
    run_at: datetime
    status: str
    records_found: int
    records_new: int
    error_message: str | None
    duration_seconds: float | None
    triggered_by: str
    portal_code: str | None = None
    portal_name: str | None = None


# --- Reports ------------------------------------------------------------------------

class ReportGenerateRequest(BaseModel):
    report_type: str = Field(pattern="^(daily|weekly|custom)$")
    file_format: str = Field(default="pdf", pattern="^(pdf|csv|xlsx)$")
    date_from: date | None = None
    date_to: date | None = None
    portal_code: str | None = None
    category: str | None = None
    state: str | None = None
    min_score: float | None = Field(default=None, ge=0, le=100)


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    report_type: str
    file_format: str
    date_range_start: date | None
    date_range_end: date | None
    filters_json: dict
    tender_count: int
    generated_at: datetime


# --- Notifications -------------------------------------------------------------------

class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    title: str
    body: str | None
    tender_ids_json: list
    channel: str
    status: str
    is_read: bool
    sent_at: datetime | None
    created_at: datetime


# --- Admin ------------------------------------------------------------------------------

class AdminUserUpdate(BaseModel):
    tier: str | None = Field(default=None, pattern="^(free|pro)$")
    is_active: bool | None = None
    is_verified: bool | None = None
    role: str | None = Field(default=None, pattern="^(user|superadmin)$")


class BlacklistIn(BaseModel):
    term: str
    reason: str | None = Field(default=None, max_length=255)

    @field_validator("term")
    @classmethod
    def _validate_term(cls, v):
        return validate_keyword(v)
