"""Lightweight scheduler — runs forever, dispatches periodic Django jobs.

Designed as a small alternative to celery beat for projects that don't
need a full task broker. Each job is a single management command that's
idempotent on its own. The loop sleeps in 60-second ticks and fires a
job when the configured schedule matches the current minute.

Schedules (Africa/Khartoum local time, configured in settings):
  - 02:00 daily         → `run_motivation_engine`     (XP + streak rolls,
                                                       comeback emails)
  - 03:00 daily         → admin daily summary digest
  - Mon 09:00 weekly    → `run_motivation_engine --weekly`  (per-user summary)
  - Mon 09:30 weekly    → admin weekly summary

Failures are logged and never crash the loop.
"""
from __future__ import annotations

import logging
import os
import sys
import time
from datetime import datetime, timedelta

# Bootstrap Django.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

import django  # noqa: E402

django.setup()

from django.core.management import call_command  # noqa: E402
from django.utils import timezone  # noqa: E402

logging.basicConfig(
    level=os.environ.get("DJANGO_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s scheduler %(message)s",
)
log = logging.getLogger("scheduler")


def _run(name: str, *args, **opts) -> None:
    log.info("→ %s %s %s", name, args, opts)
    try:
        call_command(name, *args, **opts)
    except Exception as e:
        log.exception("%s failed: %s", name, e)


def fire(now) -> None:
    """Decide which jobs (if any) should run at this minute."""
    hh, mm = now.hour, now.minute
    weekday = now.weekday()  # Monday = 0

    if hh == 2 and mm == 0:
        _run("run_motivation_engine")

    if hh == 2 and mm == 30:
        _run("compute_behavior_metrics")

    if hh == 2 and mm == 45:
        # Rotate / seed today's challenges and rebuild the leaderboard.
        try:
            from motivation.services import challenge_service, leaderboard_service
            challenge_service.rotate_weekly()
            leaderboard_service.rebuild_all()
        except Exception as e:
            log.exception("challenge/leaderboard refresh failed: %s", e)

    if hh == 3 and mm == 0:
        try:
            from notifications.services.digest_service import DigestService
            DigestService().send_daily_admin_summary()
        except Exception as e:
            log.exception("admin daily summary failed: %s", e)

    if hh == 3 and mm == 30:
        # Privacy: purge raw audio blobs older than SPEECH_AUDIO_RETENTION_DAYS.
        # Transcripts + duration + confidence stay on the SpeakingAttempt row.
        _run("clean_old_voice_recordings")

    if hh == 4 and mm == 0:
        # Subscription state machine — flip `active` to `expired` once
        # the expiry timestamp passes, send the warning email window.
        _run("expire_subscriptions")

    if hh == 4 and mm == 15:
        _run("send_subscription_expiring")

    if hh == 4 and mm == 30:
        # Drop unverified signups older than 24h — bots leave them behind.
        # Real students normally verify within minutes.
        _run("prune_unverified_users")

    if hh == 6 and mm == 0:
        # Morning nudge — today's daily-plan reminder email to every
        # active student (plan-ready / comeback / streak variant).
        _run("send_daily_learning_reminders", all_active=True)

    if hh == 6 and mm == 30:
        # Per-teacher daily digest of pending work (submissions to
        # review, content awaiting revision).
        _run("send_teacher_digests")

    if weekday == 0 and hh == 9 and mm == 0:
        _run("run_motivation_engine", weekly=True)

    if weekday == 0 and hh == 9 and mm == 30:
        try:
            from notifications.services.digest_service import DigestService
            DigestService().send_weekly_admin_summary()
        except Exception as e:
            log.exception("admin weekly summary failed: %s", e)


def main() -> int:
    log.info("scheduler started; tz=%s", timezone.get_current_timezone_name())
    last_minute = None
    while True:
        try:
            now = timezone.localtime()
            current_minute = now.replace(second=0, microsecond=0)
            if current_minute != last_minute:
                last_minute = current_minute
                fire(now)
        except Exception as e:
            log.exception("tick failed: %s", e)
        time.sleep(20)


if __name__ == "__main__":
    sys.exit(main() or 0)
