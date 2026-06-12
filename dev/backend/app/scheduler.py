"""Background jobs (APScheduler):

- portal scraping        : hourly tick, honours each portal's own interval
- daily digests          : hourly tick, fires at each user's configured IST hour
- weekly reports         : Mondays 08:00 IST for opted-in users
- archiver               : daily, moves tenders older than ARCHIVE_AFTER_DAYS

Run in-process with the API (SCHEDULER_ENABLED=true) or standalone:
    python -m app.scheduler
"""
import logging
from datetime import timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.blocking import BlockingScheduler
from sqlalchemy import select

from .config import settings
from .database import SessionLocal
from .models import Notification, PortalSource, User
from .utils.timeutil import ist_now, utcnow

logger = logging.getLogger("tenderradar.scheduler")


def _scrape_due_portals() -> None:
    from .services import scrape_service

    db = SessionLocal()
    try:
        portals = db.scalars(
            select(PortalSource).where(PortalSource.is_active.is_(True))
        ).all()
        now = utcnow()
        for portal in portals:
            interval = portal.scrape_interval_hours or settings.scrape_interval_hours
            due = (portal.last_scraped_at is None
                   or portal.last_scraped_at <= now - timedelta(hours=interval))
            if due:
                scrape_service.run_portal_scrape(db, portal, triggered_by="scheduler")
    except Exception:
        logger.exception("Scheduled scrape tick failed")
    finally:
        db.close()


def _send_digests() -> None:
    from .services import scrape_service

    db = SessionLocal()
    try:
        sent = scrape_service.run_daily_digests(db)
        if sent:
            logger.info("Sent %d daily digests", sent)
    except Exception:
        logger.exception("Digest job failed")
    finally:
        db.close()


def _weekly_reports() -> None:
    """Mondays 08:00 IST — auto-generate & email the weekly report."""
    now_ist = ist_now()
    if now_ist.weekday() != 0 or now_ist.hour != 8:
        return
    from .services.email_service import send_email
    from .services.report_service import generate_report

    db = SessionLocal()
    try:
        users = db.scalars(
            select(User).where(User.is_active.is_(True),
                               User.weekly_report_enabled.is_(True))
        ).all()
        for user in users:
            try:
                report = generate_report(db, user, report_type="weekly", file_format="pdf")
                send_email(
                    user.email,
                    "📊 TenderRadar — Your Weekly Intelligence Report",
                    f"<p>Your weekly tender intelligence report is ready "
                    f"({report.tender_count} tenders). Download it from the "
                    f"<a href='{settings.frontend_origin}/reports'>Reports page</a>.</p>",
                )
                db.add(Notification(
                    user_id=user.id, type="system", channel="email",
                    title=f"Weekly report generated ({report.tender_count} tenders)",
                    status="sent", sent_at=utcnow(),
                ))
                db.commit()
            except Exception:
                logger.exception("Weekly report failed for user %s", user.id)
                db.rollback()
    finally:
        db.close()


def _archive_old() -> None:
    from .services import scrape_service

    db = SessionLocal()
    try:
        scrape_service.archive_old_tenders(db)
    except Exception:
        logger.exception("Archive job failed")
    finally:
        db.close()


def create_scheduler(blocking: bool = False):
    sched = BlockingScheduler(timezone="UTC") if blocking else BackgroundScheduler(timezone="UTC")
    # Kick the first scrape ~30s after start in BOTH modes. (Passing
    # next_run_time=None to APScheduler adds the job *paused* — it would never
    # run — so the dedicated scheduler container must get a real first-run time.)
    sched.add_job(_scrape_due_portals, "interval", hours=1, id="scrape",
                  next_run_time=utcnow() + timedelta(seconds=30),
                  max_instances=1, coalesce=True)
    sched.add_job(_send_digests, "cron", minute=5, id="digests",
                  max_instances=1, coalesce=True)
    sched.add_job(_weekly_reports, "cron", minute=10, id="weekly_reports",
                  max_instances=1, coalesce=True)
    # 02:00 IST == 20:30 UTC
    sched.add_job(_archive_old, "cron", hour=20, minute=30, id="archiver",
                  max_instances=1, coalesce=True)
    return sched


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s — %(message)s")
    logger.info("Starting standalone TenderRadar scheduler…")
    create_scheduler(blocking=True).start()
