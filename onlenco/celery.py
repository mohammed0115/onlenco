"""Celery application stub.

The project does not require Celery to function. This module sets up an
optional Celery app so a future deployment can swap synchronous
notification dispatch for an async task without code changes elsewhere.

Activate by:
1. `pip install celery>=5`
2. set `CELERY_BROKER_URL=redis://...` in env
3. add to `onlenco/__init__.py`:
       from .celery import app as celery_app
       __all__ = ("celery_app",)
4. run worker: `celery -A onlenco worker -l info`
"""
from __future__ import annotations

import os

try:
    from celery import Celery  # type: ignore
except ImportError:  # pragma: no cover
    Celery = None  # noqa


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

app = None
if Celery is not None:
    app = Celery("onlenco")
    app.config_from_object("django.conf:settings", namespace="CELERY")
    app.autodiscover_tasks()
