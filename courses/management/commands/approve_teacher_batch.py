"""Prompt 13 — Teacher Approval Batch 1.

Approve a small batch of reviewed lessons via the REVIEW WORKFLOW SERVICE
(never raw status edits — that would bypass the audit trail). Transitions
pending_review -> in_review -> approved. NEVER publishes.

    python manage.py approve_teacher_batch --course=onlenco-beginner --topics=2-6 --dry-run
    python manage.py approve_teacher_batch --course=onlenco-beginner --topics=2-6 --confirm [--actor=<username>]

Guards (a topic is SKIPPED, never force-approved):
  * quality checker reports any error flag
  * quality_score < 90
It refuses to publish and writes start_review + approve audit events per topic.
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from courses.models import Lesson
from courses.services import content_quality_checker as qc
from courses.services import lesson_review_workflow as wf

User = get_user_model()

MIN_SCORE = 90
REVIEW_NOTE = (
    "Teacher QA Batch 1 reviewed. Content, Arabic support, challenge, skills, "
    "media prompts, and checklist passed."
)


def _parse_topics(spec: str) -> list[int]:
    spec = (spec or "").strip()
    if "-" in spec:
        lo, hi = spec.split("-", 1)
        return list(range(int(lo), int(hi) + 1))
    return [int(x) for x in spec.split(",") if x.strip()]


def _resolve_actor(username: str | None):
    if username:
        u = User.objects.filter(username=username).first()
        if not u:
            raise CommandError(f"--actor user '{username}' not found.")
        return u
    return (User.objects.filter(is_superuser=True).first()
            or User.objects.filter(is_staff=True).first())


class Command(BaseCommand):
    help = "Approve a batch of reviewed lessons via the review workflow service (no publish)."

    def add_arguments(self, parser):
        parser.add_argument("--course", required=True)
        parser.add_argument("--topics", required=True, help="e.g. 2-6 or 2,3,4")
        parser.add_argument("--dry-run", action="store_true", dest="dry_run")
        parser.add_argument("--confirm", action="store_true", dest="confirm")
        parser.add_argument("--actor", default=None)

    def handle(self, *args, **opts):
        dry_run = opts["dry_run"] or not opts["confirm"]
        orders = _parse_topics(opts["topics"])
        actor = None if dry_run else _resolve_actor(opts["actor"])
        if not dry_run and actor is None:
            raise CommandError("No actor available (pass --actor or create a staff user).")

        reviewed = approved = skipped = failed = 0
        self.stdout.write(f"Batch approval — course={opts['course']} topics={orders} "
                          f"mode={'DRY-RUN' if dry_run else 'CONFIRM'}")

        for order in orders:
            L = Lesson.objects.filter(
                course__slug=opts["course"], order=order, status="pending_review").first()
            if L is None:
                self.stdout.write(self.style.WARNING(
                    f"  T{order}: no pending_review lesson found — skipped."))
                skipped += 1
                continue
            reviewed += 1
            result = qc.check_lesson_quality(L)
            errors = [f for f in result["flags"] if f["severity"] == "error"]
            before = L.status

            if errors:
                self.stdout.write(self.style.WARNING(
                    f"  T{order} '{L.title}': SKIP — {len(errors)} error flag(s)."))
                skipped += 1
                continue
            if result["score"] < MIN_SCORE:
                self.stdout.write(self.style.WARNING(
                    f"  T{order} '{L.title}': SKIP — score {result['score']} < {MIN_SCORE}."))
                skipped += 1
                continue

            if dry_run:
                self.stdout.write(
                    f"  T{order} '{L.title}': would approve "
                    f"(score={result['score']}, {before} -> approved). No change.")
                continue

            try:
                wf.start_review(actor=actor, lesson=L, note="Batch 1 review started.")
                wf.approve(actor=actor, lesson=L, note=REVIEW_NOTE)
                L.refresh_from_db()
                assert L.status == "approved", "post-condition: status must be approved"
                self.stdout.write(self.style.SUCCESS(
                    f"  T{order} '{L.title}': {before} -> {L.status} "
                    f"(score={L.quality_score}, approved_by={getattr(actor,'username','?')})"))
                approved += 1
            except Exception as exc:  # never crash the batch — report & continue
                failed += 1
                self.stdout.write(self.style.ERROR(f"  T{order} '{L.title}': FAILED — {exc}"))

        self.stdout.write(self.style.SUCCESS(
            f"\nSummary: reviewed={reviewed} approved={approved} skipped={skipped} failed={failed} "
            f"(published=0 — this command never publishes)."))
