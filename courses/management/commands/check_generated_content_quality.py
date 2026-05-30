"""Run the content quality checker on Onlenco lessons.

Defaults to the `onlenco-beginner` course; pass --course=... to scope
elsewhere. By default prints a human report; pass --json for machine
output. Use --save to persist scores + flags onto the Lesson rows
(also writes a `quality_check` LessonReviewEvent per lesson).

Examples:
    python manage.py check_generated_content_quality
    python manage.py check_generated_content_quality --topic=12 --save
    python manage.py check_generated_content_quality --json --fail-on-errors
"""
from __future__ import annotations

import json as _json

from django.core.management.base import BaseCommand

from courses.models import Course, Lesson
from courses.services import (
    content_quality_checker, lesson_review_workflow,
)


class Command(BaseCommand):
    help = "Run the content quality checker on generated lessons."

    def add_arguments(self, parser):
        parser.add_argument("--course", default="onlenco-beginner",
                            help="Course slug to scope (default: onlenco-beginner).")
        parser.add_argument("--topic", type=int, default=0,
                            help="Only check this single topic order.")
        parser.add_argument("--save", action="store_true",
                            help="Persist score + flags onto the Lesson + audit event.")
        parser.add_argument("--json", action="store_true",
                            help="Emit JSON instead of the human report.")
        parser.add_argument("--fail-on-errors", action="store_true",
                            help="Exit code != 0 if any error-level flag fires.")

    def handle(self, *args, **opts):
        try:
            course = Course.objects.get(slug=opts["course"])
        except Course.DoesNotExist:
            self.stderr.write(self.style.ERROR(
                f"Course '{opts['course']}' not found."
            ))
            return

        qs = Lesson.objects.filter(course=course).order_by("order")
        if opts["topic"]:
            qs = qs.filter(order=opts["topic"])

        rows: list[dict] = []
        any_errors = False
        for lesson in qs:
            result = content_quality_checker.check_lesson_quality(lesson)
            rows.append({
                "lesson_id": lesson.pk,
                "order":     lesson.order,
                "title":     lesson.title,
                "status":    lesson.status,
                "score":     result["score"],
                "passed":    result["passed"],
                "flags_count": len(result["flags"]),
                "errors":    sum(1 for f in result["flags"] if f["severity"] == "error"),
                "warnings":  sum(1 for f in result["flags"] if f["severity"] == "warning"),
                "flags":     result["flags"],
            })
            if rows[-1]["errors"]:
                any_errors = True

            if opts["save"]:
                content_quality_checker.save_quality_result(lesson, result)
                lesson_review_workflow.record_quality_check(
                    actor=None, lesson=lesson,
                    score=result["score"], flags_count=len(result["flags"]),
                )

        if opts["json"]:
            self.stdout.write(_json.dumps(rows, ensure_ascii=False, indent=2))
        else:
            self._print_human_report(rows)

        if opts["fail_on_errors"] and any_errors:
            self.stderr.write(self.style.ERROR(
                "Errors detected — exiting with status 1."
            ))
            raise SystemExit(1)

    def _print_human_report(self, rows: list[dict]):
        self.stdout.write(self.style.SUCCESS(
            f"Quality check: {len(rows)} lesson(s)\n"
        ))
        worst = sorted(rows, key=lambda r: r["score"])[:5]
        for r in rows:
            status_chip = ("✅" if r["passed"] else "❌")
            line = (
                f"  {status_chip} T{r['order']:02d} {r['title'][:48]:48s} "
                f"score={r['score']:>3} "
                f"errors={r['errors']:>2} warnings={r['warnings']:>2} "
                f"({r['status']})"
            )
            self.stdout.write(line)
        self.stdout.write("\nTop 5 lowest:")
        for r in worst:
            self.stdout.write(f"  T{r['order']:02d} score={r['score']} flags={r['flags_count']}")
