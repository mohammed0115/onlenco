# Onlenco — Deployment

## Single-host (docker-compose)

```
cp .env.example .env
# fill in DJANGO_SECRET_KEY, DJANGO_ALLOWED_HOSTS, AI_API_KEY, POSTGRES_*
docker compose build
docker compose up -d
docker compose exec web python manage.py migrate
docker compose exec web python manage.py seed_learning_core
docker compose exec web python manage.py createsuperuser
```

The base compose file runs one `web`, one `db`, one `redis`. Health is at
`/healthz/`. Static assets are served by whitenoise.

## Production overlay (scaling)

The web service is stateless — scale horizontally:

```
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

The overlay sets `replicas: 3` and resource limits. Adjust `GUNICORN_WORKERS`
and `GUNICORN_THREADS` env vars to tune per-replica concurrency.

For Kubernetes: convert each service into a Deployment, set up an HPA on the
web Deployment keyed on CPU >70%, run db as a StatefulSet (or use managed
Postgres), redis as a Deployment, and put a single Celery worker Deployment
behind the same image when async generation lands.

## Backups

```
BACKUP_DIR=/var/backups/onlenco scripts/backup.sh
```

Schedule via host cron (preferred) or as a sidecar container. The script:

- `pg_dump` of the configured Postgres, gzipped
- `tar.gz` of the media directory
- prunes anything older than `BACKUP_RETENTION_DAYS` (default 14)

## Rolling deploys

1. Build a new image: `docker compose build web`
2. `docker compose up -d --no-deps --scale web=N web` rotates replicas.
3. Run `manage.py migrate` from one container before the next deploy.

## Observability

- Web logs: stdout (collected by your Docker log driver)
- Health: `GET /healthz/` returns `{"status":"ok"}` (also wired into the
  Dockerfile HEALTHCHECK).
- AI usage: `core.AIUsageLog` table — query directly or expose to the admin
  analytics dashboard.
- Login attempts: `axes_*` tables (django-axes).

## Rate limit & abuse protection

- DRF scoped throttles on `analyze-text`, `exercises/generate`,
  `tutor/chat`, `placement/*` (see `REST_FRAMEWORK.DEFAULT_THROTTLE_RATES`
  in `config/settings/base.py`).
- django-axes per-IP+username brute-force lockout
  (`AXES_FAILURE_LIMIT=5`, `AXES_COOLOFF_HOURS=1`).
- `/api/v1/auth/token/` is the mobile auth endpoint; tokens never expire by
  default — issue a delete on `Token` rows to revoke.

## Production secrets checklist

- [ ] `DJANGO_SECRET_KEY` is at least 50 random characters
- [ ] `DJANGO_DEBUG=0`
- [ ] `DJANGO_ALLOWED_HOSTS` set to the real domains
- [ ] `DJANGO_DATABASE_URL` (or POSTGRES_* split) populated
- [ ] `AI_API_KEY` present (or accept the deterministic fallbacks)
- [ ] TLS terminator in front of gunicorn sets `X-Forwarded-Proto: https`
