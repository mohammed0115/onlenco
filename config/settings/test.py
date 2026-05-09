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

# Tutor: run post-chat hooks synchronously in tests so UserError /
# UserWeakness side-effects are observable inside the test transaction
# (background threads can't see the in-progress test DB rollback).
TUTOR_HOOKS_SYNC = True
