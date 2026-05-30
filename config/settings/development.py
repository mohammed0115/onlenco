from .base import *

DEBUG = True
ALLOWED_HOSTS = ALLOWED_HOSTS or ["127.0.0.1", "localhost"]
CSRF_TRUSTED_ORIGINS = CSRF_TRUSTED_ORIGINS or ["http://127.0.0.1:8000", "http://localhost:8000"]

SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 0

# Dev: relax django-axes so retrying a few times doesn't lock you out
# during local testing. Production still uses the strict base defaults.
AXES_FAILURE_LIMIT = 50
AXES_COOLOFF_TIME = 0.05   # 3 minutes
AXES_RESET_ON_SUCCESS = True
