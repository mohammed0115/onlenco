"""Signals: grant the one-shot free trial on new User creation.

We trigger from the same post_save signal used by accounts.models —
once the user exists, drop in a FreeTrialUsage row. Idempotent via
``get_or_create``, so re-firing (or running the backfill migration on
top of new signups) never duplicates rows.
"""
from __future__ import annotations

import logging

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import FreeTrialUsage


logger = logging.getLogger(__name__)

FREE_TRIAL_SECONDS = 5 * 60  # spec: 5 minutes one-shot


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def grant_free_trial_on_user_creation(sender, instance, created, raw=False, **kwargs):
    # Skip fixture loading (raw=True): the FreeTrialUsage row comes from the
    # fixture itself, so auto-creating here collides on the OneToOne user_id.
    if not created or raw:
        return
    try:
        FreeTrialUsage.objects.get_or_create(
            user=instance,
            defaults={"free_seconds_granted": FREE_TRIAL_SECONDS},
        )
    except Exception:
        logger.exception("Failed to grant AI-Tutor free trial to user %s", instance.pk)
