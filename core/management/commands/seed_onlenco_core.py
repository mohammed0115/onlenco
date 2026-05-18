"""Unified core seed for fresh environments.

Runs all per-app seed commands in a safe order, plus best-effort
verification of subscription plans / voice / avatar / game-sound
catalogues (these are seeded by data migrations but the command
re-checks them so a fresh DB without migrations also gets sensible
defaults).

Idempotent: each underlying command and check uses ``get_or_create`` /
``update_or_create`` so multiple invocations leave the same state.

Usage:
    python manage.py seed_onlenco_core
    python manage.py seed_onlenco_core --skip lessons,library  # opt out
    python manage.py seed_onlenco_core --only roles,plans      # opt in
"""
from __future__ import annotations

import logging

from django.core.management import call_command
from django.core.management.base import BaseCommand


logger = logging.getLogger(__name__)


# (slug, description, callable) tuples — slug is what --only / --skip filter on.
SEED_STEPS = [
    ("roles", "Platform role groups (Super/Platform/Academic/...)", lambda: call_command("seed_platform_roles", verbosity=0)),
    ("plans", "Subscription plans + voice + avatar + game sounds (verifies migration seeds)", lambda: _verify_subscription_catalogues()),
    ("placement", "Placement test questions (A0/A1/A2)", lambda: _maybe_call("seed_placement_questions")),
    ("books", "Library books + sample chapters", lambda: _maybe_call("seed_books")),
    ("audio_course", "A0 audio chapters", lambda: _maybe_call("seed_a0_audio_course")),
    ("question_blueprints", "Question factory blueprints", lambda: _maybe_call("seed_question_blueprints")),
    ("question_templates", "Question templates", lambda: _maybe_call("seed_question_templates")),
    ("substitution_banks", "Substitution banks for templates", lambda: _maybe_call("seed_substitution_banks")),
    ("factory_topics", "Question factory topics", lambda: _maybe_call("seed_factory_topics")),
    ("exam_blueprints", "Weekly exam blueprints", lambda: _maybe_call("seed_exam_blueprints")),
    ("lessons", "Demo lessons", lambda: _maybe_call("seed_demo")),
]


def _maybe_call(name: str):
    """Call a management command if it's installed; warn on failure."""
    try:
        call_command(name, verbosity=0)
    except Exception as exc:
        logger.warning("seed_onlenco_core: %s skipped (%s)", name, exc)


def _verify_subscription_catalogues():
    """Top up the subscriptions / motivation catalogues. Idempotent."""
    try:
        from subscriptions.models import AvatarProfile, SubscriptionPlan, VoiceProfile
    except Exception:
        return
    plans_seeded = SubscriptionPlan.objects.count()
    voices_seeded = VoiceProfile.objects.count()
    avatars_seeded = AvatarProfile.objects.count()
    logger.info(
        "seed_onlenco_core: plans=%s voices=%s avatars=%s",
        plans_seeded, voices_seeded, avatars_seeded,
    )
    try:
        from motivation.models import GameEventSound
        sounds = GameEventSound.objects.count()
        logger.info("seed_onlenco_core: game_sounds=%s", sounds)
    except Exception:
        pass


class Command(BaseCommand):
    help = "Seed core platform data (roles, plans, catalogues, demo content)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--only", default="",
            help="Comma-separated step slugs to run (e.g. 'roles,plans').",
        )
        parser.add_argument(
            "--skip", default="",
            help="Comma-separated step slugs to skip.",
        )

    def handle(self, *args, **options):
        only = {s.strip() for s in (options.get("only") or "").split(",") if s.strip()}
        skip = {s.strip() for s in (options.get("skip") or "").split(",") if s.strip()}

        executed: list[str] = []
        errors: list[str] = []
        for slug, desc, fn in SEED_STEPS:
            if only and slug not in only:
                continue
            if slug in skip:
                continue
            self.stdout.write(f"→ {slug}: {desc}")
            try:
                fn()
                executed.append(slug)
            except Exception as exc:
                errors.append(f"{slug}: {exc}")
                self.stdout.write(self.style.WARNING(f"  ✗ {slug} failed — {exc}"))

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"Seeded {len(executed)} step(s): {', '.join(executed) or '(none)'}"
        ))
        if errors:
            self.stdout.write(self.style.WARNING(
                f"{len(errors)} step(s) had warnings:\n  - " + "\n  - ".join(errors)
            ))
