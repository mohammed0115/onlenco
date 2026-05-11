import os
from pathlib import Path


def load_dotenv() -> None:
    env_file = os.environ.get("ONLENCO_ENV_FILE", ".env")
    candidate = Path(env_file)
    if not candidate.is_absolute():
        candidate = BASE_DIR / env_file
    if not candidate.exists():
        return

    for raw_line in candidate.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def env_get(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name, default)


def env_bool(name: str, default: bool = False) -> bool:
    raw = str(env_get(name, "1" if default else "0")).strip().lower()
    return raw in {"1", "true", "yes", "on"}


def env_list(name: str, default: list[str] | None = None) -> list[str]:
    raw = env_get(name)
    if raw is None or not raw.strip():
        return list(default or [])
    return [item.strip() for item in raw.split(",") if item.strip()]


BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv()

SECRET_KEY = env_get("DJANGO_SECRET_KEY") or "local-dev-only-change-me"
DEBUG = env_bool("DJANGO_DEBUG", False)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", ["127.0.0.1", "localhost"])
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS", ["http://127.0.0.1:8000", "http://localhost:8000"])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework.authtoken",
    "drf_spectacular",
    "axes",
    "django_otp",
    "django_otp.plugins.otp_totp",
    "django_otp.plugins.otp_static",
    "accounts",
    "core",
    "lessons",
    "placement",
    "payments",
    "tutor",
    "library",
    "dictionary",
    "club",
    "analytics",
    "learning_core",
    "notifications",
    "motivation",
    "exams",
    "factory",
    "question_factory",
    "ai_training",
    "ai_engine",
    "courses",
    "speech",
]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "core.authentication.ExpiringTokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.AnonRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "user": "300/hour",
        "anon": "60/hour",
        "ai_analyze_text": "30/hour",
        "ai_exercise_gen": "20/hour",
        "ai_tutor_chat": "120/hour",
        "ai_placement": "10/hour",
    },
}

API_TOKEN_MAX_AGE_DAYS = int(env_get("API_TOKEN_MAX_AGE_DAYS", "30") or 30)

SPECTACULAR_SETTINGS = {
    "TITLE": "Onlenco API",
    "DESCRIPTION": "Adaptive English learning API",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "ENUM_NAME_OVERRIDES": {
        "CefrLevelEnum": "accounts.models.CEFR_CHOICES",
    },
}

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django_otp.middleware.OTPMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "accounts.middleware.LanguagePreferenceMiddleware",
    "accounts.middleware.ExpireSubscriptionMiddleware",
    "axes.middleware.AxesMiddleware",
]

# Opt-in: set ENABLE_2FA_ADMIN=1 to require staff to verify TOTP before
# reaching /admin/. Off by default so existing admins don't get locked out
# the moment the package is installed. When enabled, swap the admin site
# below so OTPAdminSite gates access.
ENABLE_2FA_ADMIN = env_bool("ENABLE_2FA_ADMIN", False)

AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]

# django-axes
AXES_FAILURE_LIMIT = int(env_get("AXES_FAILURE_LIMIT", "5"))
AXES_COOLOFF_TIME = float(env_get("AXES_COOLOFF_HOURS", "1.0"))
AXES_LOCKOUT_PARAMETERS = ["ip_address", "username"]
AXES_RESET_ON_SUCCESS = True

ROOT_URLCONF = "onlenco.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.i18n",
                "core.context_processors.site_context",
            ],
        },
    },
]

WSGI_APPLICATION = "onlenco.wsgi.application"
ASGI_APPLICATION = "onlenco.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 6},
    }
]

# Project default is Arabic — the primary audience is Arabic-speaking
# learners. Authenticated users override via `Profile.preferred_language`
# through `LanguagePreferenceMiddleware`. AR is listed first so the
# language toggle in the header surfaces it as the primary option.
LANGUAGE_CODE = "ar"
LANGUAGES = [
    ("ar", "العربية"),
    ("en", "English"),
]
LOCALE_PATHS = [BASE_DIR / "locale"]
TIME_ZONE = "Africa/Khartoum"
USE_I18N = True
USE_TZ = True

STATIC_URL = env_get("DJANGO_STATIC_URL", "/static/")
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
# Use the non-manifest variant: whitenoise still gzip/brotli-compresses, but
# we don't depend on `staticfiles.json` existing post-collectstatic. Switch
# back to CompressedManifestStaticFilesStorage when you want hashed filenames
# for cache-busting and the deploy pipeline is solid.
STATICFILES_STORAGE = "whitenoise.storage.CompressedStaticFilesStorage"

MEDIA_URL = env_get("DJANGO_MEDIA_URL", "/media/")
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "/auth/"
LOGIN_REDIRECT_URL = "/dashboard/"
LOGOUT_REDIRECT_URL = "/"

AI_API_KEY = env_get("AI_API_KEY", "")
AI_API_BASE = env_get("AI_API_BASE", "https://api.openai.com/v1")

# Speech / voice
# Number of days to retain raw audio uploads (SpeakingAttempt.audio_file).
# Transcripts + duration + confidence stay forever; the raw audio is the
# privacy-sensitive part and gets purged on the schedule below.
SPEECH_AUDIO_RETENTION_DAYS = int(env_get("SPEECH_AUDIO_RETENTION_DAYS", "7") or 7)
AI_MODEL = env_get("AI_MODEL", "gpt-4o-mini")

# --- Realtime voice tutor (OpenAI Realtime API) ------------------------
# Drives the live phone-call style tutoring page. Browser opens a
# WebRTC peer to OpenAI Realtime; the server only ever sees the
# ephemeral token request and the final usage stats.
AI_REALTIME_MODEL = env_get("AI_REALTIME_MODEL", "gpt-4o-realtime-preview-2024-12-17")
AI_REALTIME_VOICE = env_get("AI_REALTIME_VOICE", "alloy")
# Soft cap: per-user daily voice-call minutes. Past this threshold the
# session endpoint refuses with `limit_reached` and the user is nudged
# back to the text chat (which is unmetered).
AI_REALTIME_DAILY_MINUTE_CAP = int(env_get("AI_REALTIME_DAILY_MINUTE_CAP", "30") or 30)
# Hard cap on a single session length so a forgotten tab doesn't burn
# minutes for hours. Server returns this to the browser; browser
# auto-ends when reached.
AI_REALTIME_MAX_SESSION_SECONDS = int(env_get("AI_REALTIME_MAX_SESSION_SECONDS", "900") or 900)

# --- ai_engine local providers -----------------------------------------
# Set AI_LOCAL_CLASSIFIER_ENABLED=1 in env to let the router try local
# classifiers before falling through to LLMs. Per-task model paths are
# resolved at first-call time.
AI_LOCAL_CLASSIFIER_ENABLED = env_get("AI_LOCAL_CLASSIFIER_ENABLED", "0") == "1"
AI_DIFFICULTY_MODEL_PATH = env_get(
    "AI_DIFFICULTY_MODEL_PATH",
    str(BASE_DIR / "local_models" / "difficulty_estimator" / "v0" / "model.joblib"),
)
AI_DIFFICULTY_MODEL_VERSION = env_get("AI_DIFFICULTY_MODEL_VERSION", "v0-ridge")
AI_CEFR_MODEL_PATH = env_get(
    "AI_CEFR_MODEL_PATH",
    str(BASE_DIR / "local_models" / "cefr_classifier" / "v0" / "model.joblib"),
)
AI_CEFR_MODEL_VERSION = env_get("AI_CEFR_MODEL_VERSION", "v0-logreg")

FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024

EMAIL_BACKEND = env_get("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = env_get("EMAIL_HOST", "localhost")
EMAIL_PORT = int(env_get("EMAIL_PORT", "25"))
EMAIL_HOST_USER = env_get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env_get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", False)
DEFAULT_FROM_EMAIL = env_get("DEFAULT_FROM_EMAIL", "Onlenco <info@onlenco.com>")
# Friendly display name used by EmailService when DEFAULT_FROM_EMAIL is bare.
EMAIL_BRAND_NAME = env_get("EMAIL_BRAND_NAME", "Onlenco")
# Force every outbound email to a single language regardless of per-user
# preference. "" = honour user preference (default). "ar" = always Arabic.
# "en" = always English. Useful when the platform is single-locale.
EMAIL_FORCE_LANGUAGE = env_get("EMAIL_FORCE_LANGUAGE", "")
# Where users' replies should land when they hit "Reply" on an Onlenco
# email. Leave blank to omit the Reply-To header.
EMAIL_REPLY_TO = env_get("EMAIL_REPLY_TO", "")
# Public base URL used for HTTPS-hosted assets in email bodies (logo
# fallback, CTA links). Provider strips of CID images hit this URL.
ONLENCO_BASE_URL = env_get("ONLENCO_BASE_URL", "")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {
            "format": "%(levelname)s %(asctime)s %(name)s %(message)s",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
        }
    },
    "root": {
        "handlers": ["console"],
        "level": env_get("DJANGO_LOG_LEVEL", "INFO"),
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": env_get("DJANGO_LOG_LEVEL", "INFO"),
            "propagate": False,
        }
    },
}
