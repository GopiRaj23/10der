#!/bin/bash

set -e

echo "=== TenderRadar Docker Diagnostic ==="
echo ""

echo "1. Checking docker-compose status..."
docker compose ps
echo ""

echo "2. Checking nginx container logs..."
docker compose logs nginx --tail=20
echo ""

echo "3. Checking frontend container logs..."
docker compose logs frontend --tail=20
echo ""

echo "4. Checking backend container logs..."
docker compose logs backend --tail=20
echo ""

echo "5. Testing backend health endpoint..."
docker compose exec backend curl -s http://backend:8000/health || echo "Backend not responding"
echo ""

echo "6. Testing frontend from nginx container..."
docker compose exec nginx curl -s http://frontend:80/ | head -20 || echo "Frontend not responding"
echo ""

echo "7. Testing API endpoint through nginx..."
docker compose exec nginx curl -s http://backend:8000/health || echo "Backend not responding"
echo ""

echo "8. Checking container network..."
docker compose exec nginx ping -c 1 frontend || echo "Cannot reach frontend from nginx"
echo ""

echo "=== End Diagnostic ==="
