"""Remove internal/debug strings that may have been persisted into lesson
content (defensive — the live bug was a leaking template comment, but old DB
content could still hold copies).

    python manage.py scrub_internal_lesson_text --dry-run
    python manage.py scrub_internal_lesson_text --confirm

Scrubs only Lesson text fields (content_html / content_ar / content_en /
transcript). NEVER touches status / publish / approval flags. Idempotent —
running twice changes nothing the second time. Preserves educational content;
only known internal markers are removed.
"""
from __future__ import annotations

import re

from django.core.management.base import BaseCommand

from courses.models import Lesson

TEXT_FIELDS = ["content_html", "content_ar", "content_en", "transcript"]

# Known internal/debug markers that must never reach students. Each is matched
# narrowly so real educational copy is left intact.
PATTERNS = [
    re.compile(r"\{#.*?#\}", re.DOTALL),                       # leaked Django comment
    re.compile(r"\{%\s*comment\s*%\}.*?\{%\s*endcomment\s*%\}", re.DOTALL | re.IGNORECASE),
    re.compile(r"Phase\s*9\.5[^\n<]*", re.IGNORECASE),
    re.compile(r"Visual placeholder for steps[^\n<]*", re.IGNORECASE),
    re.compile(r"NEVER renders the raw prompt[^\n<]*", re.IGNORECASE),
    re.compile(r"associated\s+LessonImagePrompt[^\n<]*", re.IGNORECASE),
]


class Command(BaseCommand):
    help = "Scrub internal/debug markers from lesson text fields (idempotent, status-safe)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", dest="dry_run")
        parser.add_argument("--confirm", action="store_true")

    def handle(self, *args, **opts):
        dry_run = opts["dry_run"] or not opts["confirm"]
        changed_ids = []
        for lesson in Lesson.objects.all().iterator():
            dirty_fields = []
            for field in TEXT_FIELDS:
                original = getattr(lesson, field, "") or ""
                scrubbed = original
                for pat in PATTERNS:
                    scrubbed = pat.sub("", scrubbed)
                if scrubbed != original:
                    dirty_fields.append(field)
                    if not dry_run:
                        setattr(lesson, field, scrubbed)
            if dirty_fields:
                changed_ids.append(lesson.pk)
                self.stdout.write(
                    f"  lesson #{lesson.pk} ({lesson.status}): scrubbed {', '.join(dirty_fields)}"
                    + ("  [DRY]" if dry_run else "")
                )
                if not dry_run:
                    # update_fields restricted to text — status/flags untouched.
                    lesson.save(update_fields=dirty_fields + ["updated_at"] if hasattr(lesson, "updated_at") else dirty_fields)

        self.stdout.write(self.style.SUCCESS(
            f"\n[{'DRY-RUN' if dry_run else 'DONE'}] {len(changed_ids)} lesson(s) "
            f"{'would be' if dry_run else 'were'} scrubbed (status/flags untouched)."
        ))
