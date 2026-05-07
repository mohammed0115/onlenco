# Onlenco — Deployment to sudaschool.academy (187.124.9.244)

End-to-end deploy guide. The default path uses Docker + Caddy (auto TLS).
A bare-metal Nginx alternative is in the appendix.

## 0. Prerequisites — DNS + firewall

Before you SSH in, set two A records at your DNS registrar:

| Host | Type | Value | TTL |
|---|---|---|---|
| `sudaschool.academy` | A | `187.124.9.244` | 300 |
| `www.sudaschool.academy` | A | `187.124.9.244` | 300 |

Verify (from your laptop):

```
dig +short sudaschool.academy
dig +short www.sudaschool.academy
```

Both must resolve to `187.124.9.244` before Caddy can fetch a Let's Encrypt cert.

Open ports `22`, `80`, `443` on the server (the deploy script does this with ufw).

## 1. SSH in and run the bootstrap script

```
ssh root@187.124.9.244
# or your normal sudo-able user

REPO_URL=git@github.com:YOUR_ORG/onlenco.git \
  bash <(curl -fsSL https://raw.githubusercontent.com/YOUR_ORG/onlenco/main/scripts/deploy.sh)
```

If the repo is private, copy it first then run:

```
sudo apt-get install -y git
git clone https://github.com/YOUR_ORG/onlenco.git /opt/onlenco
cd /opt/onlenco
REPO_URL=$(git remote get-url origin) ./scripts/deploy.sh
```

The script:

1. Installs Docker + Compose plugin if missing.
2. Opens firewall ports 22, 80, 443.
3. Creates the `onlenco` system user, clones the repo to `/opt/onlenco`.
4. On first run, drops `.env` and exits so you can edit secrets.

## 2. Edit `/opt/onlenco/.env`

Replace every `<CHANGE_ME>`:

```
sudo -u onlenco $EDITOR /opt/onlenco/.env
```

**Required:**

```
DJANGO_SECRET_KEY=<run: python -c "import secrets; print(secrets.token_urlsafe(64))">
POSTGRES_PASSWORD=<random 24+ chars>
DEFAULT_FROM_EMAIL=Onlenco <no-reply@sudaschool.academy>
EMAIL_HOST=<your SMTP host>
EMAIL_HOST_USER=<your SMTP user>
EMAIL_HOST_PASSWORD=<your SMTP password>
ACME_EMAIL=admin@sudaschool.academy   # for Let's Encrypt notices
```

**Optional but recommended:**

```
AI_API_KEY=<your OpenAI-compatible key>   # leave empty to use deterministic fallbacks
ENABLE_2FA_ADMIN=1                         # require TOTP for /admin/
```

## 3. Re-run the deploy script

```
cd /opt/onlenco
./scripts/deploy.sh
```

This time it builds the Docker image, starts `web`, `db`, `redis`, and `caddy`,
runs migrations, seeds learning_core data, and collects static files.

Caddy will request a Let's Encrypt cert for both names automatically. First
boot can take 30–60 seconds while the cert is issued.

## 4. Create your first admin user

```
cd /opt/onlenco
sudo -u onlenco docker compose exec -it web python manage.py createsuperuser
```

Visit `https://sudaschool.academy/admin/` and sign in.

If `ENABLE_2FA_ADMIN=1`, enrol a TOTP device:

1. Visit `/admin/otp_totp/totpdevice/add/` while signed in
2. Scan the QR code with Google Authenticator or 1Password
3. Sign out and sign back in — you'll be prompted for the 6-digit code

## 5. Verify everything

```
# Health endpoint
curl -fsS https://sudaschool.academy/healthz/      # → {"status":"ok"}

# OpenAPI
curl -fsS https://sudaschool.academy/api/v1/schema/

# Container logs
sudo -u onlenco docker compose logs --tail=100 web
sudo -u onlenco docker compose logs --tail=20 caddy

# Inside the container
sudo -u onlenco docker compose exec web python manage.py check --deploy
sudo -u onlenco docker compose exec web python manage.py test --verbosity=0
```

## 6. Daily operations

### Update to latest code

```
cd /opt/onlenco
sudo -u onlenco git pull
sudo -u onlenco docker compose -f docker-compose.yml -f docker-compose.deploy.yml \
    up -d --build
sudo -u onlenco docker compose exec -T web python manage.py migrate
```

### Backups (cron-friendly)

The repo ships [scripts/backup.sh](../scripts/backup.sh). Add to root crontab:

```
0 3 * * *  cd /opt/onlenco && BACKUP_DIR=/var/backups/onlenco \
    docker compose exec -T db sh -c \
    "PGPASSWORD=$POSTGRES_PASSWORD pg_dump -U $POSTGRES_USER $POSTGRES_DB" \
    | gzip > /var/backups/onlenco/db_$(date +\%Y-\%m-\%d).sql.gz
```

Push the backup directory to S3 / Backblaze B2 nightly.

### Scheduled emails (notifications app)

Add to the `onlenco` user's crontab:

```
crontab -u onlenco -e

# Every morning at 08:00 — students whose plan expires in 3 days
0 8 * * *   cd /opt/onlenco && docker compose exec -T web python manage.py send_subscription_expiring --days 3

# Every Monday at 08:00 — students inactive for 14+ days
0 8 * * 1   cd /opt/onlenco && docker compose exec -T web python manage.py send_inactive_reminders --days 14

# Daily admin summary at 09:00
0 9 * * *   cd /opt/onlenco && docker compose exec -T web python manage.py send_admin_digests --window daily

# Weekly admin summary every Monday 09:30
30 9 * * 1  cd /opt/onlenco && docker compose exec -T web python manage.py send_admin_digests --window weekly --include-at-risk
```

### Logs you should watch

| Stream | Where |
|---|---|
| Application logs | `docker compose logs -f web` |
| TLS / proxy logs | `docker compose logs -f caddy` |
| AI usage | DB table `core_aiusagelog`, or admin → AI Usage Log |
| Brute force lockouts | `axes_*` tables, or admin → Axes |
| Email delivery audit | admin → Email Notifications |

## 7. Cost-control switches

| Setting | What it does |
|---|---|
| `AI_API_KEY=""` | Falls back to the deterministic engine — no spend. |
| `core.services.ai_usage.DAILY_LIMITS` | Per-feature daily caps for free / premium tiers. |
| `REST_FRAMEWORK.DEFAULT_THROTTLE_RATES` (`base.py`) | Per-endpoint rate limits. |

## 8. Disabling 2FA temporarily

If you lock yourself out of `/admin/`:

```
sudo -u onlenco docker compose exec web python manage.py shell -c "
from django.contrib.auth import get_user_model
u = get_user_model().objects.get(username='admin')
u.is_staff = True; u.save()
"
# Then in .env set ENABLE_2FA_ADMIN=0 and:
sudo -u onlenco docker compose up -d web
```

---

## Appendix A — Bare-metal Nginx (alternative to Caddy)

If you'd rather use Nginx + certbot directly on the host:

```
sudo apt install nginx certbot python3-certbot-nginx
sudo cp /opt/onlenco/deploy/nginx.conf /etc/nginx/sites-available/sudaschool.academy
sudo ln -s /etc/nginx/sites-available/sudaschool.academy /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

sudo certbot --nginx -d sudaschool.academy -d www.sudaschool.academy
```

Then bind gunicorn to `127.0.0.1:8000`. Edit `docker-compose.yml`:

```yaml
services:
  web:
    ports:
      - "127.0.0.1:8000:8000"
```

Don't include `docker-compose.deploy.yml` (it adds Caddy you don't need).

## Appendix B — Sanity-checking the production settings

```
DJANGO_SETTINGS_MODULE=config.settings.production \
DJANGO_SECRET_KEY=$(python3 -c "import secrets;print(secrets.token_urlsafe(64))") \
DJANGO_ALLOWED_HOSTS=sudaschool.academy,www.sudaschool.academy \
python manage.py check --deploy
```

Expected output: `System check identified no issues (0 silenced).`
