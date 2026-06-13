"""Archive every course EXCEPT the canonical CEFR ladder (A0–C2).

The catalog accumulated old/duplicate/demo courses (9-lesson early versions,
``demo-*``, ``smoke-course``) that sit at the same levels as the full 48-lesson
courses and confuse students (they may land on an empty/half-built one). This
command archives the non-canonical ones so each level shows exactly ONE clean
course. Archiving (status=archived, is_active=False) hides them from students
but keeps the data — fully reversible. Use ``--delete`` only for a hard wipe.

Safe + idempotent. Dry-run by default.

    python manage.py archive_noncanonical_courses              # preview
    python manage.py archive_noncanonical_courses --confirm    # apply (archive)
    python manage.py archive_noncanonical_courses --confirm --delete   # hard delete
"""
from django.core.management.base import BaseCommand

from courses.models import Course


# The 7 full courses (48 lessons each) that form the student-facing ladder.
CANONICAL_SLUGS = [
    "onlenco-beginner",            # A0
    "onlenco-elementary",          # A1
    "onlenco-pre-intermediate",    # A2
    "onlenco-intermediate",        # B1
    "onlenco-upper-intermediate",  # B2
    "onlenco-advanced",            # C1
    "onlenco-mastery",             # C2
]


class Command(BaseCommand):
    help = "Archive all courses except the canonical A0–C2 ladder (one clean course per level)."

    def add_arguments(self, parser):
        parser.add_argument("--confirm", action="store_true",
                            help="Apply the change (default is a dry-run preview).")
        parser.add_argument("--keep", nargs="*", default=None,
                            help="Override the keep-list of course slugs.")
        parser.add_argument("--delete", action="store_true",
                            help="DELETE the non-canonical courses instead of archiving (irreversible).")

    def handle(self, *args, **opts):
        keep = set(opts["keep"] or CANONICAL_SLUGS)
        targets = list(Course.objects.exclude(slug__in=keep).order_by("level__order", "slug"))

        present_keep = set(Course.objects.filter(slug__in=keep).values_list("slug", flat=True))
        missing = sorted(keep - present_keep)

        self.stdout.write(self.style.MIGRATE_HEADING(
            f"Keep {len(present_keep)} canonical course(s): {sorted(present_keep)}"))
        if missing:
            self.stdout.write(self.style.WARNING(f"  (keep-list slugs not found: {missing})"))

        action = "DELETE" if opts["delete"] else "Archive"
        self.stdout.write(f"{action} {len(targets)} non-canonical course(s):")
        for c in targets:
            lvl = c.level.code if c.level_id else "?"
            self.stdout.write(f"  - [{lvl}] {c.slug}  (status={c.status})")

        if not opts["confirm"]:
            self.stdout.write(self.style.WARNING(
                "DRY-RUN — nothing changed. Re-run with --confirm to apply."))
            return

        if opts["delete"]:
            count = len(targets)
            Course.objects.exclude(slug__in=keep).delete()
            self.stdout.write(self.style.SUCCESS(f"Deleted {count} course(s)."))
            return

        changed = 0
        for c in targets:
            if c.status != "archived" or c.is_active:
                c.status = "archived"
                c.is_active = False
                c.save(update_fields=["status", "is_active"])
                changed += 1
        self.stdout.write(self.style.SUCCESS(
            f"Archived {changed} course(s). Each level now shows one canonical course."))
