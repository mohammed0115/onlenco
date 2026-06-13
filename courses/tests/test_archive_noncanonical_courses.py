"""archive_noncanonical_courses: keep the A0–C2 ladder, hide the rest."""
from django.core.management import call_command
from django.test import TestCase

from courses.models import Course, CourseLevel


class ArchiveNonCanonicalCoursesTests(TestCase):
    def setUp(self):
        self.level, _ = CourseLevel.objects.get_or_create(
            code="A0", defaults={"name": "Beginner", "order": 0})
        self.canonical = Course.objects.create(
            title="Beginner", slug="onlenco-beginner", level=self.level,
            status="published", is_active=True)
        self.cruft = Course.objects.create(
            title="Old A0", slug="onlenco-a0", level=self.level,
            status="published", is_active=True)
        self.demo = Course.objects.create(
            title="Demo", slug="smoke-course", level=self.level,
            status="published", is_active=True)

    def test_dry_run_changes_nothing(self):
        call_command("archive_noncanonical_courses")
        self.cruft.refresh_from_db()
        self.assertEqual(self.cruft.status, "published")

    def test_confirm_archives_only_non_canonical(self):
        call_command("archive_noncanonical_courses", "--confirm")
        self.canonical.refresh_from_db()
        self.cruft.refresh_from_db()
        self.demo.refresh_from_db()
        self.assertEqual(self.canonical.status, "published")   # kept
        self.assertEqual(self.cruft.status, "archived")        # hidden
        self.assertFalse(self.cruft.is_active)
        self.assertEqual(self.demo.status, "archived")

    def test_archived_courses_drop_out_of_student_queryset(self):
        from courses.services.student_flow import published_course_queryset
        call_command("archive_noncanonical_courses", "--confirm")
        slugs = set(published_course_queryset().values_list("slug", flat=True))
        self.assertIn("onlenco-beginner", slugs)
        self.assertNotIn("onlenco-a0", slugs)
        self.assertNotIn("smoke-course", slugs)

    def test_delete_mode_removes_non_canonical(self):
        call_command("archive_noncanonical_courses", "--confirm", "--delete")
        self.assertTrue(Course.objects.filter(slug="onlenco-beginner").exists())
        self.assertFalse(Course.objects.filter(slug="onlenco-a0").exists())
