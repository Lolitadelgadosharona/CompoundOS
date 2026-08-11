# Production Deployment — CompoundOS V1

## Prerequisites

- Hetzner CX22 VPS (or any Ubuntu 22.04 VM with ≥2GB RAM)
- Domain name pointing to VPS IP
- Docker and Docker Compose installed
- Alpha Vantage API key (free tier: alphavantage.co)

---

## 1. VPS Preparation

```bash
# Update system
apt update && apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sh
usermod -aG docker $USER

# Install Docker Compose
apt install -y docker-compose-plugin
```

---

## 2. Clone and Configure

```bash
git clone https://github.com/Lolitadelgadosharona/CompoundOS.git
cd CompoundOS

# Create production .env
cat > .env << 'EOF'
# Required
DB_PASSWORD=<generate-strong-password>
DOMAIN=compoundos.yourdomain.com
CADDY_EMAIL=you@yourdomain.com

# API Keys (from Sprint 013)
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
AV_API_KEY=...
X_API_KEY=<generate-strong-key>

# Environment
ENVIRONMENT=production
EOF
```

---

## 3. Deploy

```bash
# Build and start all services
docker compose up -d --build

# Run database migrations
docker compose exec api alembic upgrade head

# Verify health
curl https://$DOMAIN/health
# Expected: {"status": "healthy"}
```

---

## 4. Services

| Service | Port | Description |
|---|---|---|
| API | 8000 (internal) | FastAPI backend |
| PostgreSQL | 5432 (internal) | Production database |
| Redis | 6379 (internal) | Cache / queue |
| Caddy | 80/443 (public) | Reverse proxy + HTTPS |

---

## 5. Database Migrations

```bash
# Apply migrations
docker compose exec api alembic upgrade head

# Check current revision
docker compose exec api alembic current

# Rollback one migration
docker compose exec api alembic downgrade -1
```

---

## 6. Backup

### Manual Backup
```bash
docker compose exec api scripts/backup.sh
```

### Automated Daily Backup
Add to crontab on host:
```
0 2 * * * cd /opt/CompoundOS && docker compose exec -T api scripts/backup.sh
```

### Restore Verification
```bash
# Restore to a temporary database
gunzip -c backups/compoundos_20260811_020000.sql.gz | \
  docker compose exec -T db psql -U compoundos -d compoundos_restore_test

# Verify table counts
docker compose exec db psql -U compoundos -d compoundos_restore_test \
  -c "SELECT count(*) FROM household_profiles"

# Clean up
docker compose exec db dropdb -U compoundos compoundos_restore_test
```

---

## 7. Off-Site Backup (Backblaze B2)

```bash
# Install rclone
curl https://rclone.org/install.sh | bash

# Configure (interactive)
rclone config

# Daily sync
rclone sync /opt/CompoundOS/backups b2:compoundos-backups
```

---

## 8. Monitoring

### Health Check
```
GET /health → {"status": "healthy", "db": "connected"}
```

### UptimeRobot
- URL: https://compoundos.yourdomain.com/health
- Interval: 5 minutes
- Alert: email on DOWN

### Logs
```bash
# All services
docker compose logs -f

# API only
docker compose logs -f api

# Last 100 lines
docker compose logs --tail=100 api
```

---

## 9. Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| DB_PASSWORD | Yes | — | PostgreSQL password |
| DOMAIN | Yes | — | Public domain name |
| CADDY_EMAIL | Yes | — | Let's Encrypt email |
| ANTHROPIC_API_KEY | No | — | Claude API key |
| OPENAI_API_KEY | No | — | GPT-4o API key |
| AV_API_KEY | No | — | Alpha Vantage key |
| X_API_KEY | Production | — | API auth key |
| ENVIRONMENT | No | production | Environment name |

---

## 10. Troubleshooting

### API won't start
```bash
docker compose logs api
# Common: missing DB_PASSWORD, DB not ready
```

### HTTPS not working
```bash
# Check DNS
dig compoundos.yourdomain.com

# Check Caddy
docker compose logs caddy
```

### Database connection refused
```bash
docker compose exec db pg_isready -U compoundos
```
