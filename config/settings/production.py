from .base import *

DEBUG = False

if SECRET_KEY == "local-dev-only-change-me":
    raise RuntimeError("DJANGO_SECRET_KEY must be set in production")

if not ALLOWED_HOSTS:
    raise RuntimeError("DJANGO_ALLOWED_HOSTS must be set in production")

if env_get("DJANGO_DATABASE_URL"):
    try:
        import dj_database_url
    except ImportError as exc:
        raise RuntimeError("Install dj-database-url to use DJANGO_DATABASE_URL") from exc

    DATABASES["default"] = dj_database_url.parse(
        env_get("DJANGO_DATABASE_URL"),
        conn_max_age=int(env_get("DJANGO_DB_CONN_MAX_AGE", "60")),
        ssl_require=env_bool("DJANGO_DB_SSL_REQUIRE", True),
    )
else:
    if not env_get("POSTGRES_PASSWORD"):
        raise RuntimeError("POSTGRES_PASSWORD must be set in production")

    DATABASES["default"] = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env_get("POSTGRES_DB", "onlenco"),
        "USER": env_get("POSTGRES_USER", "onlenco"),
        "PASSWORD": env_get("POSTGRES_PASSWORD", ""),
        "HOST": env_get("POSTGRES_HOST", "127.0.0.1"),
        "PORT": env_get("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": int(env_get("DJANGO_DB_CONN_MAX_AGE", "60")),
    }

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
# Probes (Caddy active healthcheck, Docker HEALTHCHECK) hit /healthz/
# directly over HTTP on the docker network, without X-Forwarded-Proto.
# Without this exempt, SECURE_SSL_REDIRECT bounces them to https://web:8000
# and the upstream gets marked unhealthy → 503 for real users.
SECURE_REDIRECT_EXEMPT = [r"^healthz/?$"]
SECURE_HSTS_SECONDS = int(env_get("DJANGO_SECURE_HSTS_SECONDS", "31536000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", True)
SECURE_HSTS_PRELOAD = env_bool("DJANGO_SECURE_HSTS_PRELOAD", True)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False  # CSRF must be readable by JS for some flows
SECURE_REFERRER_POLICY = "same-origin"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
