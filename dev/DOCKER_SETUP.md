# Docker Quick Start

## Prerequisites
- Docker and Docker Compose installed
- Port 80 available (nginx reverse proxy)

## Setup Steps

### 1. Create .env File
```bash
cp .env.example .env
```

**Important:** The `.env` file must exist before running `docker compose up`. It contains database credentials, API keys, and other configuration.

### 2. Build and Start
```bash
docker compose up --build
```

This will:
1. Build the frontend (React + Vite)
2. Build the backend (FastAPI)
3. Start PostgreSQL database
4. Run database migrations
5. Seed demo data
6. Start all services

**First run takes 1-2 minutes.** Wait for the output to settle.

### 3. Access the Application
- **Frontend:** http://localhost
- **API:** http://localhost/api/health

### Demo Credentials
Once running, log in with:
- **Email:** `demo@tenderradar.example`
- **Password:** `Demo@12345`

Or admin account:
- **Email:** `admin@tenderradar.example`
- **Password:** `Admin@12345`

## Troubleshooting

If you see "no page found error":

### Check Service Status
```bash
docker compose ps
```
All services should show "Up" status. If any show "Exited", check logs:

### View Logs
```bash
# All services
docker compose logs -f

# Specific service
docker compose logs frontend --tail=20
docker compose logs backend --tail=20
docker compose logs nginx --tail=20
```

### Common Issues

**Port 80 in use:**
```bash
# Find what's using port 80
sudo lsof -i :80

# Or restart Docker networking
docker compose restart nginx
```

**Frontend build fails:**
```bash
# Rebuild with output
docker compose build --no-cache --progress=plain frontend
```

**Database connection error:**
```bash
# Check if PostgreSQL is healthy
docker compose logs db

# Restart database
docker compose restart db
```

**Still not working?**
```bash
# Full cleanup and restart
docker compose down -v
docker compose build --no-cache
docker compose up
```

## Environment Variables

The `.env` file controls:
- **DEMO_MODE=false** (default) → scrape **real** tenders from the live portals using the
  free Scrapling engine — no API keys. Needs your machine to reach those portals. Set
  **DEMO_MODE=true** for clearly-labelled **sample** data instead (offline, first look).
- **INSTALL_BROWSER=true** (default) → required for real data: the Indian eProcurement portals
  (NIC CPPP/eTenders/state, GeM) only serve their tender list to a JavaScript browser. The image
  installs Chromium's system libs at build and **downloads the browser into a named volume on
  first run** (so it's kept out of the image and can't exhaust the Docker Desktop disk). First
  `up` takes an extra ~1–2 min while it downloads; it's cached after. Set **false** for a slim
  demo-only image.
- **DATABASE_URL** → PostgreSQL connection (overridden in compose for Docker)
- **FRONTEND_ORIGIN=http://localhost** → CORS origin for API

See `.env.example` for all available options.

### Verifying real data

The app shows a coloured banner telling you whether it's serving demo or live data. To test a
portal's live scraper directly (bypasses DEMO_MODE):

```bash
docker compose exec backend python -m app.scrapers.test_live cppp gem
```

> Note: live scraping won't work from a network that can't reach the portals. If you see
> `403 Host not in allowlist`, your environment is blocking outbound access to the portal.

## Stopping Services
```bash
# Stop all containers
docker compose down

# Stop and remove volumes (WARNING: deletes database!)
docker compose down -v
```
