"""Raw scraped-HTML storage for audit/re-parsing.

Defaults to the local filesystem (`STORAGE_DIR/raw/...`). If S3 settings are
present, uploads to the configured S3-compatible bucket instead (boto3 is an
optional dependency — install it when enabling S3).
"""
import hashlib
import logging
import os
from datetime import datetime

from ..config import settings

logger = logging.getLogger(__name__)


def store_raw_html(portal_code: str, ref_no: str, html: str | None) -> str | None:
    if not html:
        return None
    digest = hashlib.sha1(f"{portal_code}:{ref_no}".encode()).hexdigest()[:16]
    key = f"raw/{portal_code}/{datetime.utcnow():%Y%m%d}/{digest}.html"

    if settings.s3_endpoint and settings.s3_bucket:
        try:
            import boto3  # optional dependency

            client = boto3.client(
                "s3",
                endpoint_url=settings.s3_endpoint,
                aws_access_key_id=settings.s3_access_key,
                aws_secret_access_key=settings.s3_secret_key,
            )
            client.put_object(
                Bucket=settings.s3_bucket, Key=key,
                Body=html.encode("utf-8"), ContentType="text/html",
            )
            return f"s3://{settings.s3_bucket}/{key}"
        except Exception as exc:
            logger.warning("S3 upload failed (%s) — falling back to local disk", exc)

    path = os.path.join(settings.storage_dir, key)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(html)
        return path
    except OSError as exc:
        logger.error("Failed to store raw HTML: %s", exc)
        return None
