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
# AxesStandaloneBackend rejects backend authentication without one. We
# keep the backend listed (axes.W003 expects it to be present) but the
# `AXES_ENABLED = False` flag makes it a no-op for tests.
AXES_ENABLED = False
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]

# Tutor: run post-chat hooks synchronously in tests so UserError /
# UserWeakness side-effects are observable inside the test transaction
# (background threads can't see the in-progress test DB rollback).
TUTOR_HOOKS_SYNC = True

# hCaptcha: must be off in tests. When BOTH keys are present, the
# signup view enforces a CAPTCHA token in the POST body — tests don't
# carry one, so signup-related tests would falsely fail. Explicitly
# clearing both keys here keeps `_hcaptcha_verify` short-circuited.
HCAPTCHA_SITE_KEY = ""
HCAPTCHA_SECRET = ""

# Student approval gate OFF by default in tests; feature tests opt in via
# @override_settings(ONLENCO_STUDENT_APPROVAL_REQUIRED=True).
ONLENCO_STUDENT_APPROVAL_REQUIRED = False

# Isolate file storage in tests so generated-media tests do not pollute the
# real MEDIA_ROOT (Prompt 16.5 — tests write real files on .save()).
import tempfile as _tempfile
MEDIA_ROOT = _tempfile.mkdtemp(prefix="onlenco-test-media-")
