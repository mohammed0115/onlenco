from .base import *

DEBUG = False
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "test_db.sqlite3",
    }
}

ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]
CSRF_TRUSTED_ORIGINS = ["http://testserver", "http://localhost", "http://127.0.0.1"]

# Disable django-axes in tests: client.login() does not pass a request and
# AxesStandaloneBackend rejects backend authentication without one.
AXES_ENABLED = False
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
]
