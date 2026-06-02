"""Prompt 14 — Controlled Publish Pilot for Batch 1.

Publish a small batch of APPROVED lessons via the review-workflow service
(never raw status edits). Transition: approved → published. Refuses anything
that isn't a clean, approved, in-range topic. Generates NO media.

    python manage.py publish_teacher_batch --course=onlenco-beginner --topics=2-6 --dry-run
    python manage.py publish_teacher_batch --course=onlenco-beginner --topics=2-6 --confirm --actor=<email>

Guards (a topic is SKIPPED, never force-published):
  * status != approved
  * quality checker reports an error flag
  * quality_score < 90
  * archived lessons are never touched (queryset excludes them)
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from courses.models import Lesson
from courses.services import content_quality_checker as qc
from courses.services import lesson_review_workflow as wf

User = get_user_model()
MIN_SCORE = 90
PUBLISH_NOTE = ("Controlled Publish Pilot Batch 1 — approved topic published "
                "for approved students only.")


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
    help = "Publish a batch of APPROVED lessons via the review workflow (pilot)."

    def add_arguments(self, parser):
        parser.add_argument("--course", required=True)
        parser.add_argument("--topics", required=True, help="e.g. 2-6")
        parser.add_argument("--dry-run", action="store_true", dest="dry_run")
        parser.add_argument("--confirm", action="store_true", dest="confirm")
        parser.add_argument("--actor", default=None)

    def handle(self, *args, **opts):
        dry_run = opts["dry_run"] or not opts["confirm"]
        orders = _parse_topics(opts["topics"])
        actor = None if dry_run else _resolve_actor(opts["actor"])
        if not dry_run and actor is None:
            raise CommandError("No actor available (pass --actor).")

        reviewed = published = skipped = failed = 0
        self.stdout.write(f"Publish pilot — course={opts['course']} topics={orders} "
                          f"mode={'DRY-RUN' if dry_run else 'CONFIRM'}")

        for order in orders:
            # NEVER touch archived legacy lessons (exclude them explicitly).
            L = (Lesson.objects.filter(course__slug=opts["course"], order=order)
                 .exclude(status="archived").first())
            if L is None:
                self.stdout.write(self.style.WARNING(f"  T{order}: no lesson found — skipped."))
                skipped += 1
                continue
            reviewed += 1
            before = L.status
            if before != "approved":
                self.stdout.write(self.style.WARNING(
                    f"  T{order} '{L.title}': SKIP — status '{before}' (must be approved)."))
                skipped += 1
                continue
            result = qc.check_lesson_quality(L)
            if any(f["severity"] == "error" for f in result["flags"]):
                self.stdout.write(self.style.WARNING(
                    f"  T{order} '{L.title}': SKIP — error flag(s)."))
                skipped += 1
                continue
            if result["score"] < MIN_SCORE:
                self.stdout.write(self.style.WARNING(
                    f"  T{order} '{L.title}': SKIP — score {result['score']} < {MIN_SCORE}."))
                skipped += 1
                continue
            if dry_run:
                self.stdout.write(f"  T{order} '{L.title}': would publish "
                                  f"({before} → published). No change.")
                continue
            try:
                wf.publish(actor=actor, lesson=L, note=PUBLISH_NOTE)
                L.refresh_from_db()
                assert L.status == "published" and L.published_at is not None
                self.stdout.write(self.style.SUCCESS(
                    f"  T{order} '{L.title}': {before} → published "
                    f"(by {getattr(actor,'username','?')})"))
                published += 1
            except Exception as exc:
                failed += 1
                self.stdout.write(self.style.ERROR(f"  T{order} '{L.title}': FAILED — {exc}"))

        self.stdout.write(self.style.SUCCESS(
            f"\nSummary: reviewed={reviewed} published={published} skipped={skipped} "
            f"failed={failed}. No media generated."))
        self.stdout.write("Student visibility: published topics are visible ONLY to "
                          "approved students (Student Approval Gate is the boundary).")
