"""Lock / unlock courses (and single lessons) for students.

A reliable, self-reporting replacement for ad-hoc ``shell -c`` one-liners
(which silently "do nothing" when quoting/escaping breaks in a container).
This command ALWAYS prints exactly what changed.

Course-level (sets ``Course.is_free``):

    python manage.py set_course_access --all --free            # open every published course
    python manage.py set_course_access onlenco-beginner --free
    python manage.py set_course_access onlenco-elementary --paid

Lesson-level override (sets ``Lesson.access_override``):

    python manage.py set_course_access --lesson 129 --lesson-free
    python manage.py set_course_access --lesson 129 --lesson-locked
    python manage.py set_course_access --lesson 129 --lesson-inherit
"""
from django.core.management.base import BaseCommand, CommandError

from courses.models import Course, Lesson


class Command(BaseCommand):
    help = "Lock/unlock courses (is_free) or single lessons (access_override). Prints every change."

    def add_arguments(self, parser):
        parser.add_argument("slugs", nargs="*", help="Course slug(s) to update.")
        parser.add_argument("--all", action="store_true",
                            help="Apply to every PUBLISHED course.")
        parser.add_argument("--free", action="store_true",
                            help="Make the course(s) free (open to all).")
        parser.add_argument("--paid", action="store_true",
                            help="Make the course(s) paid (subscription required).")
        # Per-lesson override
        parser.add_argument("--lesson", type=int, default=None,
                            help="Lesson id for a per-lesson override.")
        parser.add_argument("--lesson-free", action="store_true",
                            help="Lesson override: free (always open).")
        parser.add_argument("--lesson-locked", action="store_true",
                            help="Lesson override: locked (subscription required).")
        parser.add_argument("--lesson-inherit", action="store_true",
                            help="Lesson override: inherit from course.")

    def handle(self, *args, **opts):
        # ----- per-lesson override branch -----
        if opts["lesson"] is not None:
            return self._handle_lesson(opts)

        # ----- course-level branch -----
        if opts["free"] == opts["paid"]:
            raise CommandError("Choose exactly one of --free or --paid.")
        make_free = opts["free"]

        if opts["all"]:
            qs = Course.objects.filter(status="published")
        elif opts["slugs"]:
            qs = Course.objects.filter(slug__in=opts["slugs"])
        else:
            raise CommandError("Pass course slug(s) or --all.")

        courses = list(qs.select_related("level").order_by("level__order", "slug"))
        if not courses:
            self.stdout.write(self.style.WARNING("No matching courses found — nothing changed."))
            if opts["slugs"]:
                existing = list(Course.objects.values_list("slug", flat=True))
                self.stdout.write(f"  (known slugs: {sorted(existing)})")
            return

        changed = 0
        for c in courses:
            lvl = c.level.code if c.level_id else "?"
            if c.is_free == make_free:
                self.stdout.write(f"  = [{lvl}] {c.slug}: already is_free={make_free}")
                continue
            c.is_free = make_free
            c.save(update_fields=["is_free", "updated_at"])
            changed += 1
            verb = "UNLOCKED (free)" if make_free else "LOCKED (paid)"
            self.stdout.write(self.style.SUCCESS(f"  ✓ [{lvl}] {c.slug}: {verb}"))

        self.stdout.write(self.style.SUCCESS(
            f"Done. Changed {changed} of {len(courses)} course(s)."))

    def _handle_lesson(self, opts):
        flags = [opts["lesson_free"], opts["lesson_locked"], opts["lesson_inherit"]]
        if sum(1 for f in flags if f) != 1:
            raise CommandError(
                "With --lesson, choose exactly one of "
                "--lesson-free / --lesson-locked / --lesson-inherit.")
        access = (Lesson.ACCESS_FREE if opts["lesson_free"]
                  else Lesson.ACCESS_LOCKED if opts["lesson_locked"]
                  else Lesson.ACCESS_INHERIT)
        try:
            lesson = Lesson.objects.select_related("course").get(pk=opts["lesson"])
        except Lesson.DoesNotExist:
            raise CommandError(f"Lesson id {opts['lesson']} not found.")
        prev = lesson.access_override
        lesson.access_override = access
        lesson.save(update_fields=["access_override", "updated_at"])
        self.stdout.write(self.style.SUCCESS(
            f"✓ Lesson {lesson.pk} ({lesson.title}) in '{lesson.course.slug}': "
            f"access_override {prev} → {access}"))
