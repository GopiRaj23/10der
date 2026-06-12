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
- **DEMO_MODE=true** → Use sample data (no real portal scraping)
- **DATABASE_URL** → PostgreSQL connection (overridden in compose for Docker)
- **FRONTEND_ORIGIN=http://localhost** → CORS origin for API

See `.env.example` for all available options.

## Stopping Services
```bash
# Stop all containers
docker compose down

# Stop and remove volumes (WARNING: deletes database!)
docker compose down -v
```
