"""Email delivery. SMTP if SMTP_HOST is set, otherwise SendGrid if an API key
is set, otherwise messages are logged to the console (dev mode) — the app
never crashes because email is unconfigured."""
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httpx
from jinja2 import Template

from ..config import settings
from ..utils.timeutil import fmt_ist

logger = logging.getLogger(__name__)

DIGEST_TEMPLATE = Template("""\
<html><body style="font-family:Arial,Helvetica,sans-serif;background:#f4f6fa;padding:24px">
<div style="max-width:640px;margin:auto;background:#fff;border-radius:8px;overflow:hidden">
  <div style="background:#0F1629;color:#fff;padding:20px 28px">
    <h2 style="margin:0">📡 TenderRadar — {{ heading }}</h2>
    <p style="margin:4px 0 0;color:#9aa4bf;font-size:13px">{{ subheading }}</p>
  </div>
  <div style="padding:20px 28px">
    {% if tenders %}
    {% for t in tenders %}
    <div style="border-bottom:1px solid #e7eaf1;padding:12px 0">
      <div style="font-size:15px;font-weight:bold;color:#0F1629">{{ t.title }}</div>
      <div style="font-size:13px;color:#555;margin-top:2px">{{ t.organisation or "—" }} · {{ t.portal_name }}</div>
      <div style="font-size:12px;color:#777;margin-top:4px">
        Closes: <b>{{ t.closing }}</b>
        &nbsp;|&nbsp; Relevance:
        <span style="color:#fff;background:{{ t.badge }};border-radius:10px;padding:1px 8px">{{ t.score }}</span>
      </div>
      <a href="{{ t.link }}" style="font-size:12px;color:#0A9396">View tender →</a>
    </div>
    {% endfor %}
    {% else %}
    <p>No new matching tenders in this period.</p>
    {% endif %}
  </div>
  <div style="padding:14px 28px;background:#f4f6fa;font-size:11px;color:#888">
    This app aggregates publicly available tender information. Always verify on the
    official portal before bidding. — Powered by TenderRadar
  </div>
</div>
</body></html>
""")


def _badge_color(score: float) -> str:
    if score >= 70:
        return "#1a7f4b"
    if score >= 40:
        return "#b7791f"
    return "#b03a2e"


def render_digest_html(heading: str, subheading: str, tenders: list[dict]) -> str:
    rows = [
        {
            "title": t["title"],
            "organisation": t.get("organisation"),
            "portal_name": t.get("portal_name", ""),
            "closing": fmt_ist(t.get("closing_date")),
            "score": t.get("relevance_score", 0),
            "badge": _badge_color(t.get("relevance_score", 0) or 0),
            "link": f"{settings.frontend_origin}/tenders/{t['id']}",
        }
        for t in tenders
    ]
    return DIGEST_TEMPLATE.render(heading=heading, subheading=subheading, tenders=rows)


def send_email(to: str, subject: str, html_body: str) -> bool:
    """Returns True when handed off to a provider (or logged in dev mode)."""
    if settings.smtp_host:
        return _send_smtp(to, subject, html_body)
    if settings.sendgrid_api_key:
        return _send_sendgrid(to, subject, html_body)
    logger.info("[EMAIL-DEV] to=%s subject=%r (no SMTP/SendGrid configured)", to, subject)
    return True


def _send_smtp(to: str, subject: str, html_body: str) -> bool:
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.email_from
        msg["To"] = to
        msg.attach(MIMEText(html_body, "html", "utf-8"))
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as server:
            server.starttls()
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(settings.email_from, [to], msg.as_string())
        return True
    except Exception as exc:
        logger.error("SMTP send failed to %s: %s", to, exc)
        return False


def _send_sendgrid(to: str, subject: str, html_body: str) -> bool:
    try:
        resp = httpx.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={"Authorization": f"Bearer {settings.sendgrid_api_key}"},
            json={
                "personalizations": [{"to": [{"email": to}]}],
                "from": {"email": settings.email_from.split("<")[-1].rstrip("> ")},
                "subject": subject,
                "content": [{"type": "text/html", "value": html_body}],
            },
            timeout=20,
        )
        return resp.status_code in (200, 202)
    except Exception as exc:
        logger.error("SendGrid send failed to %s: %s", to, exc)
        return False


def send_whatsapp_stub(number: str, message: str) -> bool:
    """WhatsApp channel is a stub ("coming soon" in the UI)."""
    logger.info("[WHATSAPP-STUB] to=%s message=%r", number, message[:120])
    return False
