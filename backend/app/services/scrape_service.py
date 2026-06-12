"""Scrape orchestration: runs portal scrapers, upserts tenders (dedup by
portal + ref-no), computes per-user keyword matches/relevance, fires instant
alerts, sends daily digests and archives stale tenders.

All entry points swallow per-portal errors — a failing scraper is logged in
`scrape_logs` and never takes the app down.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import (
    Keyword,
    Notification,
    PortalSource,
    ScrapeLog,
    Tender,
    TenderArchive,
    TenderKeywordMatch,
    User,
)
from ..scrapers.base import TenderRecord
from ..scrapers.registry import get_scraper
from ..utils.timeutil import ist_now, utcnow
from . import matching
from .cache import cache
from .email_service import render_digest_html, send_email
from .raw_storage import store_raw_html

logger = logging.getLogger(__name__)

INSTANT_ALERT_THRESHOLD = 80.0


# --- Portal scraping ----------------------------------------------------------

def run_portal_scrape(db: Session, portal: PortalSource,
                      triggered_by: str = "scheduler") -> ScrapeLog:
    """Scrape one portal end-to-end. Always returns a ScrapeLog row."""
    lock_key = f"scrape:lock:{portal.code}"
    log = ScrapeLog(portal_source_id=portal.id, status="running",
                    triggered_by=triggered_by)
    db.add(log)
    db.commit()

    if not cache.acquire_lock(lock_key, ttl=600):
        log.status = "skipped"
        log.error_message = "another scrape for this portal is already running"
        db.commit()
        return log

    started = time.monotonic()
    try:
        search_terms = _active_search_terms(db)
        scraper = get_scraper(portal)
        records, error = scraper.safe_scrape(search_terms)
        found, new_ids, all_ids = _upsert_tenders(db, portal, records)

        log.records_found = found
        log.records_new = len(new_ids)
        log.duration_seconds = round(time.monotonic() - started, 2)
        if error and not records:
            log.status = "skipped" if error.startswith("skipped:") else "failed"
            log.error_message = error
        elif error:
            log.status = "partial"
            log.error_message = error
        else:
            log.status = "success"
        portal.last_scraped_at = utcnow()
        db.commit()

        if all_ids:
            match_count, alerts = compute_matches_for_tenders(db, all_ids)
            logger.info("Portal %s: %d tenders (%d new), %d keyword matches, %d alerts",
                        portal.code, found, len(new_ids), match_count, alerts)
        return log
    except Exception as exc:  # noqa: BLE001 — isolation by design
        logger.exception("Unexpected scrape failure for %s", portal.code)
        db.rollback()
        log = db.get(ScrapeLog, log.id) or log
        log.status = "failed"
        log.error_message = str(exc)[:1000]
        log.duration_seconds = round(time.monotonic() - started, 2)
        db.commit()
        return log
    finally:
        cache.release_lock(lock_key)


def run_all_portals(db: Session, triggered_by: str = "scheduler") -> list[ScrapeLog]:
    logs = []
    portals = db.scalars(
        select(PortalSource).where(PortalSource.is_active.is_(True))
    ).all()
    for portal in portals:
        logs.append(run_portal_scrape(db, portal, triggered_by))
    return logs


def _active_search_terms(db: Session) -> list[str]:
    """Distinct active keyword texts across all users (global scrape pool)."""
    rows = db.scalars(
        select(Keyword.keyword_text)
        .join(User, Keyword.user_id == User.id)
        .where(Keyword.is_active.is_(True), User.is_active.is_(True))
        .distinct()
    ).all()
    return list(rows)


def _upsert_tenders(db: Session, portal: PortalSource,
                    records: list[TenderRecord]) -> tuple[int, list[int], list[int]]:
    """Insert-or-update by (portal, ref_no). Returns (found, new_ids, all_ids)."""
    new_ids: list[int] = []
    all_ids: list[int] = []
    for rec in records:
        if not rec.tender_ref_no or not rec.title:
            continue
        existing = db.scalar(
            select(Tender).where(
                Tender.portal_source_id == portal.id,
                Tender.tender_ref_no == rec.tender_ref_no,
            )
        )
        raw_path = store_raw_html(portal.code, rec.tender_ref_no, rec.raw_html)
        if existing:
            changed = False
            for field_name in ("title", "organisation", "department", "category",
                               "state", "published_date", "closing_date",
                               "estimated_value", "document_url", "raw_url",
                               "description_text"):
                value = getattr(rec, field_name)
                if value is not None and getattr(existing, field_name) != value:
                    setattr(existing, field_name, value)
                    changed = True
            if raw_path:
                existing.raw_html_path = raw_path
            if changed:
                existing.updated_at = utcnow()
            all_ids.append(existing.id)
        else:
            tender = Tender(
                portal_source_id=portal.id,
                tender_ref_no=rec.tender_ref_no,
                title=rec.title,
                organisation=rec.organisation,
                department=rec.department,
                category=rec.category,
                state=rec.state or portal.state,
                published_date=rec.published_date,
                closing_date=rec.closing_date,
                estimated_value=rec.estimated_value,
                document_url=rec.document_url,
                raw_url=rec.raw_url,
                description_text=rec.description_text,
                raw_html_path=raw_path,
            )
            db.add(tender)
            db.flush()
            new_ids.append(tender.id)
            all_ids.append(tender.id)
    db.commit()
    return len(records), new_ids, all_ids


# --- Keyword matching & alerts ----------------------------------------------------

def compute_matches_for_tenders(db: Session, tender_ids: list[int]) -> tuple[int, int]:
    """Score every active keyword against the given tenders. Returns
    (matches_created, instant_alerts_sent)."""
    tenders = db.scalars(select(Tender).where(Tender.id.in_(tender_ids))).all()
    keywords = db.scalars(
        select(Keyword)
        .join(User, Keyword.user_id == User.id)
        .where(Keyword.is_active.is_(True), User.is_active.is_(True))
    ).all()
    if not tenders or not keywords:
        return 0, 0

    portal_map = {p.id: p for p in db.scalars(select(PortalSource)).all()}
    users = {u.id: u for u in db.scalars(select(User)).all()}

    created = 0
    alert_payloads: list[tuple[User, Tender, Keyword, float]] = []

    for tender in tenders:
        portal = portal_map.get(tender.portal_source_id)
        for kw in keywords:
            user = users.get(kw.user_id)
            if user is None or portal is None:
                continue
            # Tier gating: free users only match free-tier portals
            if user.tier == "free" and portal.tier_required != "free":
                continue
            # Keyword-level portal selection ([] = all allowed portals)
            if kw.portals_json and portal.code not in kw.portals_json:
                continue
            score, details = matching.score_tender(
                keyword_text=kw.keyword_text,
                synonyms=kw.synonyms_json or [],
                title=tender.title,
                description=tender.description_text,
                organisation=tender.organisation,
                department=tender.department,
                tender_state=tender.state,
                user_state=user.state,
                user_industry=user.industry,
            )
            # Only persist real keyword hits (field match), not state/industry-only
            if not details["matched_fields"] or not (
                {"title", "description", "organisation"} & set(details["matched_fields"])
            ):
                continue
            existing = db.scalar(
                select(TenderKeywordMatch).where(
                    TenderKeywordMatch.tender_id == tender.id,
                    TenderKeywordMatch.keyword_id == kw.id,
                )
            )
            if existing:
                existing.relevance_score = score
                existing.match_details_json = details
            else:
                db.add(TenderKeywordMatch(
                    tender_id=tender.id, keyword_id=kw.id, user_id=user.id,
                    relevance_score=score, match_details_json=details,
                ))
                created += 1
                if score > INSTANT_ALERT_THRESHOLD and user.instant_alerts_enabled:
                    alert_payloads.append((user, tender, kw, score))
    db.commit()

    alerts = 0
    for user, tender, kw, score in alert_payloads:
        if _send_instant_alert(db, user, tender, kw, score):
            alerts += 1
    return created, alerts


def _send_instant_alert(db: Session, user: User, tender: Tender,
                        keyword: Keyword, score: float) -> bool:
    portal = db.get(PortalSource, tender.portal_source_id)
    html = render_digest_html(
        "Instant Alert — High-Relevance Tender",
        f'Keyword "{keyword.keyword_text}" matched with score {score}',
        [{
            "id": tender.id, "title": tender.title,
            "organisation": tender.organisation,
            "portal_name": portal.name if portal else "",
            "closing_date": tender.closing_date,
            "relevance_score": score,
        }],
    )
    ok = send_email(user.email, f"⚡ TenderRadar Alert: {tender.title[:80]}", html)
    db.add(Notification(
        user_id=user.id, type="instant", channel="email",
        title=f"High-relevance match ({score}): {tender.title[:200]}",
        body=f'Keyword "{keyword.keyword_text}" matched tender {tender.tender_ref_no}',
        tender_ids_json=[tender.id],
        status="sent" if ok else "failed",
        sent_at=utcnow() if ok else None,
    ))
    db.commit()
    return ok


# --- Daily digest ------------------------------------------------------------------

def run_daily_digests(db: Session) -> int:
    """Called hourly; sends the digest to users whose configured IST hour is now."""
    current_ist_hour = ist_now().hour
    today_utc = utcnow().date()
    users = db.scalars(
        select(User).where(User.is_active.is_(True), User.is_verified.is_(True))
    ).all()
    sent = 0
    for user in users:
        if user.digest_hour_ist != current_ist_hour:
            continue
        if user.last_digest_sent_at and user.last_digest_sent_at.date() == today_utc:
            continue  # already sent today
        if send_digest_for_user(db, user):
            sent += 1
    return sent


def send_digest_for_user(db: Session, user: User) -> bool:
    since = utcnow() - timedelta(hours=24)
    rows = db.execute(
        select(TenderKeywordMatch, Tender, PortalSource)
        .join(Tender, TenderKeywordMatch.tender_id == Tender.id)
        .join(PortalSource, Tender.portal_source_id == PortalSource.id)
        .where(
            TenderKeywordMatch.user_id == user.id,
            TenderKeywordMatch.created_at >= since,
            Tender.is_archived.is_(False),
        )
        .order_by(TenderKeywordMatch.relevance_score.desc(),
                  Tender.closing_date.asc())
        .limit(50)
    ).all()

    # Best score per tender, keep top 10
    best: dict[int, dict] = {}
    for match, tender, portal in rows:
        if tender.id not in best or match.relevance_score > best[tender.id]["relevance_score"]:
            best[tender.id] = {
                "id": tender.id, "title": tender.title,
                "organisation": tender.organisation, "portal_name": portal.name,
                "closing_date": tender.closing_date,
                "relevance_score": match.relevance_score,
            }
    top = sorted(best.values(), key=lambda t: (-t["relevance_score"],
                 t["closing_date"] or datetime.max))[:10]

    html = render_digest_html(
        "Your Daily Tender Digest",
        f"{len(top)} new matching tenders in the last 24 hours",
        top,
    )
    ok = send_email(user.email, "📡 TenderRadar — Your Daily Tender Digest", html)
    db.add(Notification(
        user_id=user.id, type="digest", channel="email",
        title=f"Daily digest — {len(top)} new matching tenders",
        body=None, tender_ids_json=[t["id"] for t in top],
        status="sent" if ok else "failed", sent_at=utcnow() if ok else None,
    ))
    user.last_digest_sent_at = utcnow()
    db.commit()
    return ok


# --- Archiver -----------------------------------------------------------------------

def archive_old_tenders(db: Session) -> int:
    """Move tenders older than ARCHIVE_AFTER_DAYS into tenders_archive."""
    cutoff_date = (utcnow() - timedelta(days=settings.archive_after_days)).date()
    cutoff_dt = utcnow() - timedelta(days=settings.archive_after_days)
    stale = db.scalars(
        select(Tender).where(
            func.coalesce(Tender.published_date, func.date(Tender.scraped_at)) < cutoff_date,
            Tender.scraped_at < cutoff_dt,
        )
    ).all()
    for t in stale:
        db.add(TenderArchive(
            original_tender_id=t.id, portal_source_id=t.portal_source_id,
            tender_ref_no=t.tender_ref_no, title=t.title,
            organisation=t.organisation, department=t.department,
            category=t.category, state=t.state,
            published_date=t.published_date, closing_date=t.closing_date,
            estimated_value=t.estimated_value, document_url=t.document_url,
            raw_url=t.raw_url, description_text=t.description_text,
        ))
        db.delete(t)  # FK cascades clean matches/statuses
    db.commit()
    if stale:
        logger.info("Archived %d tenders older than %d days",
                    len(stale), settings.archive_after_days)
    return len(stale)
