"""Phase 5 — library level-default + course/library separation guard."""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from courses.models import Course, CourseLevel, Lesson
from library.models import Book

User = get_user_model()


@override_settings(AXES_ENABLED=False)
class LibraryLevelDefaultTests(TestCase):
    """The library opens at the learner's own CEFR level."""

    def setUp(self):
        self.user = User.objects.create_user(username="lvlreader", password="pw")
        prof = self.user.profile
        prof.cefr_level = "A2"
        prof.save()
        self.client.force_login(self.user)
        Book.objects.create(title="A2 Book", category="novel", level="A2")
        Book.objects.create(title="B1 Book", category="novel", level="B1")

    def _titles(self, response):
        return {b.title for b in response.context["page_obj"].object_list}

    def test_first_visit_defaults_to_learner_level(self):
        resp = self.client.get(reverse("library"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self._titles(resp), {"A2 Book"})

    def test_level_all_shows_every_level(self):
        resp = self.client.get(reverse("library"), {"level": "all"})
        self.assertEqual(self._titles(resp), {"A2 Book", "B1 Book"})

    def test_explicit_level_pins_it(self):
        resp = self.client.get(reverse("library"), {"level": "B1"})
        self.assertEqual(self._titles(resp), {"B1 Book"})

    def test_no_learner_level_shows_all(self):
        prof = self.user.profile
        prof.cefr_level = ""
        prof.save()
        resp = self.client.get(reverse("library"))
        self.assertEqual(self._titles(resp), {"A2 Book", "B1 Book"})


@override_settings(AXES_ENABLED=False)
class LibraryHasNoCourseLessonsTests(TestCase):
    """Invariant guard: the library lists books only — course lessons
    must never leak into the library listing."""

    def setUp(self):
        self.user = User.objects.create_user(username="sepreader", password="pw")
        self.client.force_login(self.user)
        Book.objects.create(title="Real Library Book", category="novel", level="A1")
        level = CourseLevel.objects.create(code="A1", name="A1", order=1, is_active=True)
        course = Course.objects.create(
            title="Some Course", slug="some-course", level=level,
            status="published", is_active=True, is_free=True,
        )
        Lesson.objects.create(
            course=course, title="ZZZ_COURSE_LESSON_LEAK_CHECK", order=1,
            status="published", is_active=True,
        )

    def test_library_lists_book_objects_only(self):
        resp = self.client.get(reverse("library"), {"level": "all"})
        self.assertEqual(resp.status_code, 200)
        objects = list(resp.context["page_obj"].object_list)
        self.assertTrue(objects)
        self.assertTrue(all(isinstance(o, Book) for o in objects))

    def test_course_lesson_absent_from_library_page(self):
        resp = self.client.get(reverse("library"), {"level": "all"})
        self.assertNotContains(resp, "ZZZ_COURSE_LESSON_LEAK_CHECK")
        self.assertContains(resp, "Real Library Book")
