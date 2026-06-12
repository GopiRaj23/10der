"""TenderRadar API — FastAPI application factory."""
import logging
from contextlib import asynccontextmanager

import jwt as pyjwt
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from .config import settings
from .database import init_db
from .routers import (
    admin,
    auth,
    dashboard,
    keywords,
    portals,
    reports,
    scrape,
    tenders,
    users,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger("tenderradar")


def _rate_limit_key(request: Request) -> str:
    """Rate-limit per authenticated user, falling back to client IP."""
    header = request.headers.get("authorization", "")
    if header.startswith("Bearer "):
        try:
            payload = pyjwt.decode(header[7:], settings.jwt_secret,
                                   algorithms=[settings.jwt_algorithm])
            return f"user:{payload.get('sub')}"
        except pyjwt.InvalidTokenError:
            pass
    return get_remote_address(request)


limiter = Limiter(key_func=_rate_limit_key, default_limits=[settings.rate_limit])


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    scheduler = None
    if settings.scheduler_enabled:
        from .scheduler import create_scheduler

        scheduler = create_scheduler(blocking=False)
        scheduler.start()
        logger.info("Background scheduler started (scrape every %sh, digests hourly)",
                    settings.scrape_interval_hours)
    yield
    if scheduler:
        scheduler.shutdown(wait=False)


app = FastAPI(
    title="TenderRadar API",
    description="Indian Government Tender Aggregator — discover, filter and "
                "track tenders from 19+ procurement portals.",
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(keywords.router)
app.include_router(tenders.router)
app.include_router(tenders.share_router)
app.include_router(portals.router)
app.include_router(scrape.router)
app.include_router(reports.router)
app.include_router(dashboard.router)
app.include_router(admin.router)


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok", "app": settings.app_name, "demo_mode": settings.demo_mode}
