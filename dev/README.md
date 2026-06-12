# 📡 TenderRadar — Indian Government Tender Aggregator SaaS

TenderRadar automatically discovers, filters and tracks government tenders from **19 Indian
procurement portals** (GeM, CPPP, NIC eTenders, Defence, Railways, PSUs + 10 state portals),
matches them against each user's **business keywords** (with synonyms and AND/OR/NOT boolean
logic), scores relevance 0–100, and delivers **daily digests, instant alerts and PDF/Excel
intelligence reports**.

> ⚠️ **Disclaimer:** This app aggregates publicly available tender information.
> Always verify on the official portal before bidding.

---

## Tech stack

| Layer | Tech |
|---|---|
| Frontend | React 18 (Vite) + Tailwind CSS v4 + shadcn-style components |
| Backend | Python FastAPI + SQLAlchemy 2 + Pydantic v2 |
| Database | PostgreSQL 16 (`tsvector` full-text search) — SQLite fallback for quick hacking |
| Cache / locks | Redis 7 (graceful in-memory fallback) |
| Scraping | [Scrapling](https://github.com/D4Vinci/Scrapling) (free/open-source): Chrome TLS-impersonated HTTP + stealth headless Chromium for JS/anti-bot portals |
| Auth | JWT (15-min access / 7-day refresh) + bcrypt (12 rounds) + email verification + OTP reset |
| Jobs | APScheduler (in-process or standalone service) |
| Email | SMTP or SendGrid (console logging in dev) |
| Reports | ReportLab PDF + CSV + openpyxl XLSX |
| Deploy | Docker Compose (nginx + frontend + backend + scheduler + postgres + redis) |

> The whole application lives in the **`dev/`** subfolder of this repository.

## Quick start (Docker — recommended)

```bash
cd dev
cp .env.example .env          # then edit JWT_SECRET etc.
docker compose up --build
# → app on http://localhost  (API docs: http://localhost/api/docs)
```

The backend container runs Alembic migrations + seeds the 19 portals and demo users;
the **scheduler** service then performs the first scrape ~30s after start and hourly after.
With the default `DEMO_MODE=false` it scrapes **real** tenders (see below); set
`DEMO_MODE=true` to populate realistic **sample** data instead.

> 💡 A coloured banner at the top of the app always tells you which mode you're in, so
> demo data is never mistaken for real listings.

## Quick start (manual, no Docker)

```bash
# 1. Services: PostgreSQL 16 + Redis (or let it fall back to in-memory)
createdb tenderradar

# 2. Backend
cd dev/backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env                     # config is read from the backend CWD
python -m app.seed --scrape                 # tables + portals + demo data
uvicorn app.main:app --reload               # http://localhost:8000/docs

# 3. Frontend (separate terminal)
cd dev/frontend
npm install
npm run dev                                 # http://localhost:5173 (proxies /api → :8000)
```

### Seeded accounts

| Account | Email | Password | Notes |
|---|---|---|---|
| Superadmin | `admin@tenderradar.example` | `Admin@12345` | Admin panel access |
| Demo (Pro) | `demo@tenderradar.example` | `Demo@12345` | 6 keywords (UAV/drone/thermal…) |
| Demo (Free) | `free@tenderradar.example` | `Free@12345` | Free-tier limits demo |

> Change `ADMIN_EMAIL` / `ADMIN_PASSWORD` in `.env` before deploying anywhere real.

## Live data vs demo mode

**`DEMO_MODE=false` (default) scrapes REAL tenders** from the live portals — completely free,
no API keys, powered by [Scrapling](https://github.com/D4Vinci/Scrapling). Two requirements:

1. **Network reach** — the machine running the scraper must be able to reach the portals
   (`eprocure.gov.in`, `bidplus.gem.gov.in`, …). Run it on your own machine/server, **not** a
   locked-down CI/cloud box whose egress allowlist blocks those hosts (you'd get `403
   Host not in allowlist`).
2. **(Optional) browser for JS portals** — NIC/GePNIC portals (CPPP + 7 state portals + MoD)
   scrape via Chrome-impersonated **HTTP and need no browser**. GeM/IREPS render with JS, so
   they need a stealth headless Chromium:
   - **Local (no Docker):** run `scrapling install` once (free ~400 MB download).
   - **Docker:** set `INSTALL_BROWSER=true` in `.env` and rebuild — kept opt-in so the default
     image stays slim (a large image can exhaust a small Docker Desktop disk).

**Verify live access before trusting the app** — this calls the real scraper and prints what it
finds (bypasses `DEMO_MODE`):

```bash
cd dev/backend
python -m app.scrapers.test_live              # list testable portals
python -m app.scrapers.test_live cppp gem tn  # hit specific portals
```

`DEMO_MODE=true` flips every scraper to realistic **sample** data so the whole product —
matching, scoring, alerts, reports, dashboards, admin — is evaluable offline with zero external
dependencies. These are clearly labelled "DEMO DATA" in the UI and **will not appear on the
official portals**.

### Re-matching keywords against already-collected tenders

Adding or editing a keyword automatically re-scores it against every tender already in the
database (no scrape needed), so matches surface immediately. You can also force a full
re-match from the **Keywords → "Rescan now"** button (or `POST /keywords/rescan`). To fetch
*fresh* tenders on demand, use **`POST /scrape/trigger`** (per-portal) — the scheduler also
runs scrapes automatically on each portal's interval.

## Portal coverage

| Portal | Code | Engine | Status |
|---|---|---|---|
| CPPP eprocure.gov.in | `cppp` | impersonated HTTP + stealth-browser fallback | ✅ **reference implementation** |
| GeM bidplus.gem.gov.in | `gem` | stealth headless Chromium | ✅ **reference implementation** |
| etenders.gov.in (NIC) | `etenders-nic` | NIC parser (shared w/ CPPP) | ✅ working parse core |
| defproc.gov.in (MoD) | `defproc` | NIC parser | ✅ working parse core |
| TN / AP / MH / UP / DL / KL | `tn ap mh up dl kl` | NIC parser | ✅ working parse core |
| DRDO, IREPS, BHEL, ONGC, HAL | — | stub (`BaseScraper` interface) | 🔧 implement `scrape()` |
| Karnataka, Telangana, Gujarat, Rajasthan | — | stub | 🔧 implement `scrape()` |

All scrapers inherit `app/scrapers/base.py::BaseScraper`; failures are isolated — a broken
portal is logged to `scrape_logs` and never crashes the app. `robots.txt` is honoured when
`RESPECT_ROBOTS_TXT=true`.

## Project layout

```
dev/
├── docker-compose.yml          # nginx + frontend + backend + scheduler + db + redis
├── .env.example                # every config knob, documented
├── nginx/nginx.conf            # reverse proxy (/api → backend, / → frontend)
├── backend/
│   ├── alembic/                # migrations (0001 bootstraps schema + FTS trigger)
│   ├── app/
│   │   ├── main.py             # app factory, CORS, slowapi rate limiting, routers
│   │   ├── config.py           # pydantic-settings (.env driven)
│   │   ├── database.py         # engine/session + tsvector DDL
│   │   ├── models.py           # users, keywords, portal_sources, tenders(+archive),
│   │   │                       # matches, statuses, scrape_logs, reports, notifications
│   │   ├── schemas.py          # pydantic request/response models
│   │   ├── auth.py             # bcrypt + JWT + deps (user / superadmin)
│   │   ├── scheduler.py        # APScheduler jobs (scrape/digest/weekly/archive)
│   │   ├── seed.py             # 19 portals + admin + demo users (+ --scrape)
│   │   ├── routers/            # auth users keywords tenders portals scrape
│   │   │                       # reports dashboard admin
│   │   ├── scrapers/           # base, engine (scrapling), cppp, gem, stubs, demo, registry
│   │   ├── services/           # matching (relevance engine), scrape_service,
│   │   │                       # report_service (PDF/CSV/XLSX), email, cache, ai_summary
│   │   └── utils/              # sanitize (XSS), timeutil (UTC↔IST)
│   └── requirements.txt
└── frontend/
    └── src/
        ├── api/client.js       # fetch wrapper + JWT refresh + IST formatters
        ├── components/         # Layout (navy sidebar), TenderTable, charts, ui kit, Logo
        └── pages/              # Dashboard Search MyTenders TenderDetail Keywords
                                # Reports Alerts Settings Admin + auth pages + ShareView
```

## Key product behaviours

- **Relevance score (0–100):** title match 40 + description 30 + organisation 10 +
  user-state match 10 + industry match 10. Badges: 🟢 ≥70, 🟡 40–69, 🔴 <40.
- **Boolean keywords:** `drone AND surveillance NOT toy`, quoted phrases, parentheses;
  synonyms act as OR-alternatives for the whole keyword.
- **Dedup/upsert:** unique `(portal, tender_ref_no)`; re-scrapes update changed fields.
- **Alerts:** digest at the user's chosen IST hour; instant email when score > 80;
  WhatsApp channel stubbed ("coming soon").
- **Reports:** Daily / Weekly / Custom in PDF (colour-coded by score), CSV, XLSX;
  optional auto-email every Monday 8 AM IST.
- **Archival:** tenders older than `ARCHIVE_AFTER_DAYS` (180) move to `tenders_archive`.
- **Tiers:** Free = 3 portals + 5 keywords; Pro = everything (payment integration is a stub).
- **Security:** JWT-only endpoints, slowapi 100 req/min/user, sanitised inputs,
  parameterised queries, CORS locked to the frontend origin, admin role middleware.
- **Raw HTML audit:** scraped HTML stored under `storage/raw/` (or S3 when configured).
- **Timezones:** stored UTC, displayed IST throughout (UI + emails + PDFs).

## Migrations

```bash
cd dev/backend
alembic upgrade head                                   # apply
alembic revision --autogenerate -m "add column"        # after editing models.py
```

## API surface (summary)

`POST /auth/{register,login,refresh,forgot-password,reset-password,verify-email}` ·
`GET/PUT /users/me` · `GET /users/me/notifications` ·
`GET/POST/PUT/DELETE /keywords` · `POST /keywords/rescan` (re-match vs collected tenders) ·
`GET /config` (public: demo/live + engine flags) ·
`GET /tenders` (filters: keyword, portal, state, category, closing window, value range,
score, status, sort, pagination) · `GET /tenders/bookmarks` · `GET /tenders/{id}` ·
`POST /tenders/{id}/status` · `GET /tenders/{id}/related` · `GET /tenders/{id}/summary` ·
`POST /tenders/{id}/share` + public `GET /share/{token}` ·
`GET /portals` · `GET /portals/status` ·
`POST /scrape/trigger` · `GET /scrape/logs` ·
`GET /reports` · `POST /reports/generate` · `GET /reports/{id}/download` ·
`GET /dashboard/{stats,analytics,calendar}` ·
`GET/PUT /admin/users` · `PUT /admin/portals/{id}` · `GET /admin/{system-health,usage}` ·
`GET/POST/DELETE /admin/blacklist`

Interactive docs: `http://localhost:8000/docs` (or `/api/docs` behind nginx).
