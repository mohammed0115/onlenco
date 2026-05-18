"""Backfill: every existing user gets the one-shot 5-minute trial.

Without this, the trial only fires for accounts created after the
signup signal is wired. Existing accounts would silently be blocked
from AI Tutor after deployment because they have neither subscription
nor trial — a regression we don't want to ship.
"""
from django.db import migrations


FREE_TRIAL_SECONDS = 5 * 60


def grant_trial_to_existing_users(apps, schema_editor):
    User = apps.get_model("auth", "User")
    FreeTrialUsage = apps.get_model("subscriptions", "FreeTrialUsage")
    for user in User.objects.all().only("id"):
        FreeTrialUsage.objects.get_or_create(
            user_id=user.id,
            defaults={"free_seconds_granted": FREE_TRIAL_SECONDS},
        )


def noop_reverse(apps, schema_editor):
    """Reverse leaves rows in place — they're harmless on rollback."""
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("subscriptions", "0003_freetrialusage_aitutorsession"),
    ]
    operations = [
        migrations.RunPython(grant_trial_to_existing_users, reverse_code=noop_reverse),
    ]
