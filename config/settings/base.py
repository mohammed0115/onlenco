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
    "django.contrib.sitemaps",
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
    "daily_learning",
    "platform_admin",
    "teacher_portal",
    "subscriptions",
    "ai_usage",
]

# --- Daily Learning Engine ----------------------------------------------
# Hard cap on OpenAI / paid-provider calls per user per day from the
# daily plan generator. The generator always tries question-bank /
# template paths first; AI only fires when those return nothing AND
# this cap hasn't been hit. Set to 0 to disable AI entirely.
DAILY_LEARNING_AI_DAILY_CAP_PER_USER = int(env_get("DAILY_LEARNING_AI_DAILY_CAP_PER_USER", "1") or 1)
# Master kill-switch — if False the generator never calls ai_engine.
DAILY_LEARNING_USE_AI = env_bool("DAILY_LEARNING_USE_AI", True)
# Target number of items per daily plan. Spec says 5–8.
DAILY_LEARNING_MIN_ITEMS = 5
DAILY_LEARNING_MAX_ITEMS = 8
# Comeback plan (inactive student) is intentionally shorter.
DAILY_LEARNING_COMEBACK_ITEMS = 4
# Recent-mistakes window (days) used by review service.
DAILY_LEARNING_MISTAKE_LOOKBACK_DAYS = 7

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
    "core.security_headers.SecurityHeadersMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "core.middleware.QueryStringLanguageMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django_otp.middleware.OTPMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "accounts.middleware.LanguagePreferenceMiddleware",
    "accounts.middleware.ExpireSubscriptionMiddleware",
    "accounts.middleware.ForcePasswordChangeMiddleware",
    "accounts.middleware.StudentApprovalRequiredMiddleware",
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
        "OPTIONS": {"min_length": 8},
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

# Public canonical origin — used for canonical URLs, sitemap, robots.txt,
# Open Graph and JSON-LD. Override per environment via the SITE_URL env var.
SITE_URL = env_get("SITE_URL", "https://onlenco.academy").rstrip("/")

# Search Console domain-verification token (the value of the
# `google-site-verification` content attribute, NOT the full tag). Empty by
# default so nothing renders until it's set in the production environment.
GOOGLE_SITE_VERIFICATION = env_get("GOOGLE_SITE_VERIFICATION", "") or ""
# Google Analytics 4 measurement ID, e.g. "G-XXXXXXXXXX". When empty the GA4
# snippet is not emitted at all (no tracking, no extra requests).
GOOGLE_ANALYTICS_ID = env_get("GOOGLE_ANALYTICS_ID", "") or ""

# Live-session Google Meet integration. Off by default → the meet service
# returns a realistic mock link so scheduling works everywhere without keys.
# Set GOOGLE_MEET_ENABLED=1 and provide credentials to use the real API.
GOOGLE_MEET_ENABLED = env_bool("GOOGLE_MEET_ENABLED", False)
GOOGLE_MEET_CREDENTIALS_FILE = env_get("GOOGLE_MEET_CREDENTIALS_FILE", "") or ""
GOOGLE_MEET_CALENDAR_ID = env_get("GOOGLE_MEET_CALENDAR_ID", "primary") or "primary"

# Public social-media profiles, shown in the site footer. Each is empty by
# default and only renders when set — no placeholder/fake links.
SOCIAL_FACEBOOK_URL = env_get("SOCIAL_FACEBOOK_URL", "") or ""
SOCIAL_INSTAGRAM_URL = env_get("SOCIAL_INSTAGRAM_URL", "") or ""
SOCIAL_X_URL = env_get("SOCIAL_X_URL", "") or ""
SOCIAL_LINKEDIN_URL = env_get("SOCIAL_LINKEDIN_URL", "") or ""
SOCIAL_YOUTUBE_URL = env_get("SOCIAL_YOUTUBE_URL", "") or ""
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
AI_REALTIME_MODEL = env_get("AI_REALTIME_MODEL", "gpt-realtime")
AI_REALTIME_VOICE = env_get("AI_REALTIME_VOICE", "alloy")
# Soft cap: per-user daily voice-call minutes. Past this threshold the
# session endpoint refuses with `limit_reached` and the user is nudged
# back to the text chat (which is unmetered).
AI_REALTIME_DAILY_MINUTE_CAP = int(env_get("AI_REALTIME_DAILY_MINUTE_CAP", "30") or 30)
# Hard cap on a single session length so a forgotten tab doesn't burn
# minutes for hours. Server returns this to the browser; browser
# auto-ends when reached.
AI_REALTIME_MAX_SESSION_SECONDS = int(env_get("AI_REALTIME_MAX_SESSION_SECONDS", "300") or 300)

# --- Placement speaking (level test, Prompt 16.6F) ----------------------
# The placement SPEAKING test is part of onboarding: a brand-new student
# takes it before any subscription exists. Policy:
#   * It NEVER consumes the daily AI-Tutor minute allowance, and is never
#     blocked when those minutes are exhausted.
#   * Each student gets exactly ONE valid attempt (ONE_ATTEMPT_ONLY). A
#     re-attempt is only possible after an audited admin reset.
#   * One attempt is capped at MAX_MINUTES_PER_ATTEMPT minutes.
#   * Usage is still fully logged in ai_usage under
#     feature="placement_speaking" (never "ai_tutor").
PLACEMENT_SPEAKING_ENABLED = env_bool("PLACEMENT_SPEAKING_ENABLED", True)
PLACEMENT_SPEAKING_ONE_ATTEMPT_ONLY = env_bool("PLACEMENT_SPEAKING_ONE_ATTEMPT_ONLY", True)
PLACEMENT_SPEAKING_MAX_MINUTES_PER_ATTEMPT = int(
    env_get("PLACEMENT_SPEAKING_MAX_MINUTES_PER_ATTEMPT", "7") or 7
)
PLACEMENT_SPEAKING_ALLOW_ADMIN_RESET = env_bool("PLACEMENT_SPEAKING_ALLOW_ADMIN_RESET", True)
# Strict completion gate: the student must complete the SPEAKING section
# before the final result is shown / the course is assigned. Written-only is
# not enough. A too-short / empty / failed speaking call is retryable (it does
# not consume the one lifetime attempt). Admins can override explicitly.
PLACEMENT_REQUIRE_SPEAKING_FOR_FINAL_RESULT = env_bool(
    "PLACEMENT_REQUIRE_SPEAKING_FOR_FINAL_RESULT", True
)
# Minimum spoken answers for the speaking section to count as completed.
PLACEMENT_SPEAKING_MIN_ANSWERS = int(
    env_get("PLACEMENT_SPEAKING_MIN_ANSWERS", "3") or 3
)
# Tutor-led speaking: the tutor asks each question and retries per question
# (repeat slowly → hint → move on) before that question is "unable".
PLACEMENT_SPEAKING_MAX_RETRIES_PER_QUESTION = int(
    env_get("PLACEMENT_SPEAKING_MAX_RETRIES_PER_QUESTION", "2") or 2
)
# Max FAILED call attempts (student attempted but answered < min) before the
# section is marked unable_to_answer_after_retries and finalised conservatively
# — so a true beginner is never blocked forever.
PLACEMENT_SPEAKING_MAX_RETRIES = int(
    env_get("PLACEMENT_SPEAKING_MAX_RETRIES", "3") or 3
)
# Conservative placement when the student couldn't answer after retries:
# the speaking level and the overall ceiling stay low (this is treated as
# evidence of very low speaking ability, NOT a technical failure).
PLACEMENT_SPEAKING_UNABLE_LEVEL = env_get("PLACEMENT_SPEAKING_UNABLE_LEVEL", "A0")
PLACEMENT_FINAL_CAP_WHEN_UNABLE = env_get("PLACEMENT_FINAL_CAP_WHEN_UNABLE", "A1")
# Rough per-minute realtime cost (USD) used ONLY for the ai_usage estimate;
# real billing is reconciled monthly against the provider invoice.
PLACEMENT_SPEAKING_EST_COST_PER_MIN_USD = env_get(
    "PLACEMENT_SPEAKING_EST_COST_PER_MIN_USD", "0.30"
)
# Configurable written-percentage → CEFR level mapping (Placement Phase 5).
# Each pair is (inclusive_upper_percentage, level); the first band whose
# ceiling is >= the score wins. Override in env/settings to retune without
# touching code or templates.
PLACEMENT_LEVEL_MAP = [
    (20, "A0"), (40, "A1"), (60, "A2"), (75, "B1"),
    (88, "B2"), (95, "C1"), (100, "C2"),
]

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

# --- AI Usage Tracking & Cost Control (ai_usage app, Prompt 12A) --------
# Master switch. When False the wrapper still calls the provider and
# returns the response, but skips usage logging & minute enforcement.
AI_USAGE_TRACKING_ENABLED = env_bool("AI_USAGE_TRACKING_ENABLED", True)
AI_USAGE_DEFAULT_CURRENCY = env_get("AI_USAGE_DEFAULT_CURRENCY", "USD")
# Comma-separated list of admin emails for spend / failure alerts.
AI_USAGE_ALERT_EMAILS = env_list("AI_USAGE_ALERT_EMAILS", [])
# Budgets (strings → Decimal in the alert/dashboard services so we never
# carry float money). Empty / "0" disables that threshold.
AI_USAGE_DAILY_BUDGET_USD = env_get("AI_USAGE_DAILY_BUDGET_USD", "25")
AI_USAGE_MONTHLY_BUDGET_USD = env_get("AI_USAGE_MONTHLY_BUDGET_USD", "500")
# AI-Tutor free first-day / base plan minute defaults. Authoritative
# allowances live on SubscriptionPlan; these are the fallbacks the
# adapter uses when the subscription system can't answer.
AI_TUTOR_FREE_FIRST_DAY_MINUTES = int(env_get("AI_TUTOR_FREE_FIRST_DAY_MINUTES", "5") or 5)
AI_TUTOR_BASE_DAILY_MINUTES = int(env_get("AI_TUTOR_BASE_DAILY_MINUTES", "5") or 5)
# Privacy. Students never see internal USD cost unless this is True.
AI_USAGE_STUDENT_CAN_VIEW_COST = env_bool("AI_USAGE_STUDENT_CAN_VIEW_COST", False)
# Prompt / response storage OFF by default. If enabled, redaction applies.
AI_USAGE_LOG_PROMPTS = env_bool("AI_USAGE_LOG_PROMPTS", False)
AI_USAGE_LOG_RESPONSES = env_bool("AI_USAGE_LOG_RESPONSES", False)
AI_USAGE_REDACT_METADATA = env_bool("AI_USAGE_REDACT_METADATA", True)
# Abnormal per-user daily spend ($) that triggers an alert.
AI_USAGE_USER_DAILY_ALERT_USD = env_get("AI_USAGE_USER_DAILY_ALERT_USD", "5")
# Failed-request count per hour that triggers an alert.
AI_USAGE_FAILED_REQUESTS_ALERT = int(env_get("AI_USAGE_FAILED_REQUESTS_ALERT", "25") or 25)

# --- Student registration approval gate + anti-bot --------------------
# New students need admin approval before reaching student features.
ONLENCO_STUDENT_APPROVAL_REQUIRED = env_bool("ONLENCO_STUDENT_APPROVAL_REQUIRED", True)
# Registration honeypot field name (hidden in the form; bots fill it).
ONLENCO_REGISTRATION_HONEYPOT_FIELD = env_get("ONLENCO_REGISTRATION_HONEYPOT_FIELD", "ol_contact_url")
# CAPTCHA readiness (disabled by default; the project already supports hCaptcha
# via HCAPTCHA_SITE_KEY — these are forward-compatible toggles).
ONLENCO_REGISTRATION_CAPTCHA_ENABLED = env_bool("ONLENCO_REGISTRATION_CAPTCHA_ENABLED", False)
ONLENCO_CAPTCHA_PROVIDER = env_get("ONLENCO_CAPTCHA_PROVIDER", "turnstile")
# Disposable-email blocking (off by default).
ONLENCO_BLOCK_DISPOSABLE_EMAILS = env_bool("ONLENCO_BLOCK_DISPOSABLE_EMAILS", False)
ONLENCO_DISPOSABLE_EMAIL_DOMAINS = env_list("ONLENCO_DISPOSABLE_EMAIL_DOMAINS", [
    "mailinator.com", "guerrillamail.com", "10minutemail.com", "tempmail.com",
    "trashmail.com", "yopmail.com", "throwawaymail.com", "getnada.com",
])
# Registration rate limit (per IP per hour). The signup view already throttles;
# this constant centralises the value.
ONLENCO_REGISTRATION_RATE_LIMIT_PER_HOUR = int(
    env_get("ONLENCO_REGISTRATION_RATE_LIMIT_PER_HOUR", "10") or 10)

# --- Media Generation Pilot (Prompt 15) -------------------------------
# OFF by default — generation must be explicitly enabled (or --allow-dev-generation).
ONLENCO_MEDIA_GENERATION_ENABLED = env_bool("ONLENCO_MEDIA_GENERATION_ENABLED", False)
ONLENCO_MEDIA_PILOT_BUDGET_USD = env_get("ONLENCO_MEDIA_PILOT_BUDGET_USD", "5.00")
ONLENCO_MEDIA_MAX_IMAGES_PER_RUN = int(env_get("ONLENCO_MEDIA_MAX_IMAGES_PER_RUN", "20") or 20)
ONLENCO_MEDIA_MAX_AUDIO_PER_RUN = int(env_get("ONLENCO_MEDIA_MAX_AUDIO_PER_RUN", "30") or 30)
# Only published/approved lessons are eligible; students see media only after approval.
ONLENCO_MEDIA_REQUIRE_APPROVED_LESSON = env_bool("ONLENCO_MEDIA_REQUIRE_APPROVED_LESSON", True)
ONLENCO_MEDIA_STUDENT_VISIBLE_ONLY_AFTER_APPROVAL = env_bool(
    "ONLENCO_MEDIA_STUDENT_VISIBLE_ONLY_AFTER_APPROVAL", True)
# Pilot scope + conservative per-item cost estimates (used for budget gating
# before the real AIUsageLog cost lands).
ONLENCO_MEDIA_PILOT_TOPICS = env_get("ONLENCO_MEDIA_PILOT_TOPICS", "2-6")
ONLENCO_MEDIA_IMAGE_SIZE = env_get("ONLENCO_MEDIA_IMAGE_SIZE", "1024x1024")
ONLENCO_MEDIA_EST_COST_PER_IMAGE_USD = env_get("ONLENCO_MEDIA_EST_COST_PER_IMAGE_USD", "0.02")
ONLENCO_MEDIA_EST_COST_PER_AUDIO_USD = env_get("ONLENCO_MEDIA_EST_COST_PER_AUDIO_USD", "0.05")
# Brand / IP names that must never reach the image provider. Matched as WHOLE
# words, so the safe disclaimer "no logos / no trademarked styling" is fine —
# generic words like "logo"/"trademark" are deliberately NOT listed.
ONLENCO_MEDIA_UNSAFE_WORDS = env_list("ONLENCO_MEDIA_UNSAFE_WORDS", [
    "dk", "duolingo", "owl", "disney", "pixar", "celebrity",
])

FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024

EMAIL_BACKEND = env_get("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = env_get("EMAIL_HOST", "localhost")
EMAIL_PORT = int(env_get("EMAIL_PORT", "25"))
EMAIL_HOST_USER = env_get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env_get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", False)
# Hard cap on every SMTP socket operation. Without this an unreachable
# or slow mail server makes Django's email send hang indefinitely —
# which previously froze the whole signup request behind it.
EMAIL_TIMEOUT = int(env_get("EMAIL_TIMEOUT", "10"))
DEFAULT_FROM_EMAIL = env_get("DEFAULT_FROM_EMAIL", "Onlenco <contact@onlenco.academy>")
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

# --- Anti-bot signup protection ---------------------------------------
# Optional hCaptcha on /auth/?mode=signup. Both keys must be set to
# enable; leave empty to skip (honeypot + rate-limit still apply).
# Site key is public (rendered in HTML); secret is server-side only.
HCAPTCHA_SITE_KEY = env_get("HCAPTCHA_SITE_KEY", "")
HCAPTCHA_SECRET = env_get("HCAPTCHA_SECRET", "")
# Max signup POSTs accepted per client IP per hour — a backstop against
# automated signup floods. Kept generous: many real users in Sudan
# share one public IP via carrier-grade NAT, so a low cap (the old
# value was 5) wrongly blocked legitimate signups.
SIGNUP_RATE_LIMIT_PER_IP_PER_HOUR = int(env_get("SIGNUP_RATE_LIMIT_PER_IP_PER_HOUR", "30"))

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
