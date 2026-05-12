FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings.production \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . /app

RUN useradd --create-home --uid 1000 onlenco \
    && chown -R onlenco:onlenco /app

USER onlenco

# Collectstatic at build time so the image ships with static assets.
# Production settings refuse to load unless several env vars are set;
# we inject dummy build-only values so the settings module imports
# cleanly. None of these reach the runtime container — gunicorn uses
# the real values from `.env` (mounted via env_file in docker-compose.yml).
#
# Why each is needed (search `config/settings/production.py`):
#   DJANGO_SECRET_KEY        - production rejects the dev default
#   DJANGO_ALLOWED_HOSTS     - production rejects an empty list
#   POSTGRES_PASSWORD        - production rejects empty (added 2026-05)
#   DJANGO_SECURE_SSL_REDIRECT - off at build (no TLS terminator yet)
RUN DJANGO_SECRET_KEY=build-only-not-secret \
    DJANGO_ALLOWED_HOSTS=localhost \
    POSTGRES_PASSWORD=build-only-not-secret \
    DJANGO_SECURE_SSL_REDIRECT=0 \
    python manage.py collectstatic --noinput --clear

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/healthz/ || exit 1

CMD ["gunicorn", "onlenco.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "3", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
