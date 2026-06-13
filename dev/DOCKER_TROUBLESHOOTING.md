# Docker Troubleshooting Guide

If you're seeing "no page found error" when accessing `http://localhost`, follow these steps:

## Quick Diagnostics

1. **Check if containers are running:**
   ```bash
   docker compose ps
   ```
   All services should be in "Up" state, not "Exit" or "Exited".

2. **View container logs:**
   ```bash
   docker compose logs -f
   ```
   Look for errors in backend, frontend, or nginx.

3. **Run the diagnostic script:**
   ```bash
   bash docker-diagnose.sh
   ```

## Common Issues & Solutions

### Issue 0: Build fails with "input/output error" extracting a layer
**Symptom:** the build runs for a while then fails unpacking the image, e.g.
```
failed to extract layer ... write .../ms-playwright/chromium_headless_shell-.../chrome-headless-shell: input/output error
```
**Cause:** Docker Desktop's virtual disk ran out of space. This used to happen because
the browser was baked into the image; it's now **downloaded into a named volume at
runtime** instead, so this shouldn't recur — but if the disk is genuinely full, reclaim
space:
```bash
docker compose down
docker system prune -af          # removes stopped containers, unused images
docker builder prune -af         # removes build cache
# and/or raise Docker Desktop → Settings → Resources → Virtual disk limit
docker compose up --build
```

### Issue 0b: "stealth browser not ready" / JS portals empty
**Symptom:** the app's banner says the stealth browser isn't ready, or the scheduler logs
`browser download failed`. The Indian eProcurement portals need it for real data.
**Cause/Fix:** on first `up` the browser downloads into the `browsers` volume (~1–2 min);
just wait, then it's cached. If it keeps failing:
```bash
docker compose logs backend | grep -i entrypoint   # see the install attempt
# free Docker disk (see Issue 0), then re-trigger the install:
docker volume rm 10der_browsers 2>/dev/null || docker volume rm dev_browsers
docker compose up -d
```
Only need demo/sample data? Set `INSTALL_BROWSER=false` in `.env` to skip it entirely.

### Issue 1: Frontend Build Failed
**Symptom:** Frontend container exits immediately or shows build errors in logs
**Solution:**
```bash
# Rebuild the frontend image
docker compose build --no-cache frontend

# Check the logs
docker compose logs frontend
```

**Common build failure causes:**
- Missing `npm install` dependencies
- `npm run build` fails (check for TypeScript errors)
- Disk space full

### Issue 2: Nginx Cannot Find Frontend
**Symptom:** 502 Bad Gateway or connection refused
**Solution:**
```bash
# Check if frontend container is healthy
docker compose ps frontend

# If not running, check logs
docker compose logs frontend --tail=50

# Test connectivity between containers
docker compose exec nginx ping frontend
docker compose exec nginx curl http://frontend:80/
```

### Issue 3: Frontend Returns 404
**Symptom:** Access to `http://localhost/` returns 404
**Likely cause:** The `dist/` directory is empty or wasn't built
**Solution:**
```bash
# Rebuild with verbose output
docker compose build --no-cache --progress=plain frontend

# Check if build completed
docker compose exec frontend ls -la /usr/share/nginx/html/

# Should see index.html and assets/ directory
```

### Issue 4: Backend Not Available
**Symptom:** API calls fail (404 or 502 on /api/* endpoints)
**Solution:**
```bash
# Check backend logs
docker compose logs backend --tail=50

# Test backend directly
docker compose exec backend curl http://backend:8000/health

# Check database connectivity
docker compose logs db --tail=20

# Verify migrations ran
docker compose logs backend | grep "alembic\|Upgrades\|migrations"
```

### Issue 5: Database Migration Failed
**Symptom:** Backend exits with error about database
**Solution:**
```bash
# Check if DB is ready
docker compose logs db

# Manually run migrations
docker compose exec backend alembic upgrade head

# Reseed database
docker compose exec backend python -m app.seed --scrape
```

## Step-by-Step Fix

If nothing above works, try a clean rebuild:

```bash
# Stop all containers
docker compose down

# Remove volumes (WARNING: deletes database!)
docker compose down -v

# Rebuild everything
docker compose build --no-cache

# Start with verbose output
docker compose up

# In another terminal, check status
docker compose ps
```

## Manual Testing

Once containers are running:

```bash
# Test backend API
curl http://localhost/api/health

# Test frontend is served
curl http://localhost/ | head -20

# Check frontend built correctly
curl http://localhost/assets/ 
```

## Port Conflicts

If you get "port 80 already in use":
```bash
# Find process using port 80
sudo lsof -i :80

# Or use docker
docker ps | grep :80

# Kill the conflicting service and restart
docker compose restart nginx
```

## Logs to Check

In order of importance:
1. `docker compose logs nginx` - Reverse proxy routing issues
2. `docker compose logs frontend` - Frontend build or serving issues
3. `docker compose logs backend` - API errors, database connection issues
4. `docker compose logs db` - Database startup issues
5. `docker compose logs redis` - Cache issues (non-critical)

## Expected Service Startup Order

1. **db** (PostgreSQL) - 10-30 seconds
2. **redis** (Cache) - 2-5 seconds
3. **backend** (FastAPI)
   - Runs alembic migrations (5-10 seconds)
   - Seeds demo data (5-10 seconds)
   - Starts uvicorn server (2-5 seconds)
   - Total: 15-30 seconds
4. **frontend** (nginx SPA server) - 5-30 seconds depending on npm install
5. **scheduler** (Background jobs) - Starts after backend is ready
6. **nginx** (Reverse proxy) - 2-5 seconds

**Total time to full availability: 30-90 seconds**

## Still Stuck?

Collect this info and share it:
```bash
docker compose ps
docker compose logs
docker compose exec backend python -m app.main --version 2>/dev/null || echo "Version check failed"
docker --version
docker-compose --version
```
