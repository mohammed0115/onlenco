"""Prompt 14 — Rollback for the Controlled Publish Pilot.

Reverts published pilot lessons published → approved via the workflow service.
Students lose access; teachers/admins still see them. Deletes NOTHING
(no lessons, no attempts, no progress).

    python manage.py unpublish_teacher_batch --course=onlenco-beginner --topics=2-6 --dry-run
    python manage.py unpublish_teacher_batch --course=onlenco-beginner --topics=2-6 --confirm --actor=<email>
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from courses.models import Lesson
from courses.services import lesson_review_workflow as wf

User = get_user_model()
ROLLBACK_NOTE = "Rollback of Controlled Publish Pilot Batch 1."


def _parse_topics(spec: str) -> list[int]:
    spec = (spec or "").strip()
    if "-" in spec:
        lo, hi = spec.split("-", 1)
        return list(range(int(lo), int(hi) + 1))
    return [int(x) for x in spec.split(",") if x.strip()]


def _resolve_actor(username):
    if username:
        u = User.objects.filter(username=username).first() or User.objects.filter(email=username).first()
        if not u:
            raise CommandError(f"--actor '{username}' not found.")
        return u
    return User.objects.filter(is_superuser=True).first() or User.objects.filter(is_staff=True).first()


class Command(BaseCommand):
    help = "Rollback: unpublish a batch of pilot lessons (published → approved)."

    def add_arguments(self, parser):
        parser.add_argument("--course", required=True)
        parser.add_argument("--topics", required=True)
        parser.add_argument("--dry-run", action="store_true", dest="dry_run")
        parser.add_argument("--confirm", action="store_true", dest="confirm")
        parser.add_argument("--actor", default=None)

    def handle(self, *args, **opts):
        dry_run = opts["dry_run"] or not opts["confirm"]
        orders = _parse_topics(opts["topics"])
        actor = None if dry_run else _resolve_actor(opts["actor"])
        if not dry_run and actor is None:
            raise CommandError("No actor available (pass --actor).")

        reverted = skipped = failed = 0
        self.stdout.write(f"Rollback — course={opts['course']} topics={orders} "
                          f"mode={'DRY-RUN' if dry_run else 'CONFIRM'}")
        for order in orders:
            L = (Lesson.objects.filter(course__slug=opts["course"], order=order)
                 .exclude(status="archived").first())
            if L is None or L.status != "published":
                self.stdout.write(self.style.WARNING(
                    f"  T{order}: skip (status={getattr(L, 'status', 'missing')})."))
                skipped += 1
                continue
            if dry_run:
                self.stdout.write(f"  T{order} '{L.title}': would revert published → approved.")
                continue
            try:
                wf.unpublish(actor=actor, lesson=L, note=ROLLBACK_NOTE)
                L.refresh_from_db()
                assert L.status == "approved"
                self.stdout.write(self.style.SUCCESS(f"  T{order} '{L.title}': published → approved."))
                reverted += 1
            except Exception as exc:
                failed += 1
                self.stdout.write(self.style.ERROR(f"  T{order}: FAILED — {exc}"))

        self.stdout.write(self.style.SUCCESS(
            f"\nSummary: reverted={reverted} skipped={skipped} failed={failed}. "
            f"No progress/attempts/lessons deleted."))
