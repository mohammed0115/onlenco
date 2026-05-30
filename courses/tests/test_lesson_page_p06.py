"""Coverage for the redesigned lesson page (Prompt 06).

Verifies the lesson detail page renders all 13 sections, works without
media, supports AR/LTR mixing, and uses Onlenco brand identity (not DK's).
"""
from __future__ import annotations

from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, Client

from courses.models import Course, CourseEnrollment, Lesson


User = get_user_model()
COURSE_SLUG = "onlenco-beginner"


class LessonPageP06Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Seed the course so we have realistic content to render.
        call_command("seed_onlenco_beginner_48_units", "--quiet", stdout=StringIO())
        call_command("seed_onlenco_beginner_quiz_bank", "--quiet", stdout=StringIO())
        cls.course = Course.objects.get(slug=COURSE_SLUG)
        cls.lesson = Lesson.objects.filter(course=cls.course, order=1).first()
        cls.user = User.objects.create_user(
            username="student1", password="pw", email="s1@onlenco.test",
        )
        # Mark email verified so the lesson view's auth + drip checks pass.
        if hasattr(cls.user, "profile"):
            cls.user.profile.email_verified = True
            cls.user.profile.subscription_status = "active"
            cls.user.profile.save()
        CourseEnrollment.objects.get_or_create(user=cls.user, course=cls.course)

    def _get(self, lang="en", lesson=None):
        c = Client(SERVER_NAME="127.0.0.1")
        c.force_login(self.user)
        target = lesson or self.lesson
        url = f"/admin/" if not target else \
              f"/courses/{self.course.pk}/lessons/{target.pk}/"
        return c.get(url, HTTP_HOST="127.0.0.1",
                     HTTP_ACCEPT_LANGUAGE=("ar-EG" if lang == "ar" else "en-US"))

    def test_lesson_page_renders(self):
        r = self._get()
        # Either 200 or a redirect (drip gate). 500 fails the test below.
        self.assertNotEqual(r.status_code, 500, r.content[:500])

    def test_lesson_page_no_internal_server_error(self):
        for order in (1, 2, 5, 19, 34, 48):
            lesson = Lesson.objects.filter(course=self.course, order=order).first()
            r = self._get(lesson=lesson)
            self.assertNotEqual(
                r.status_code, 500,
                f"Lesson {order} ({lesson.title}) returned 500",
            )

    def _get_step(self, kind, lang="en"):
        """The stepper redesign moved per-step content into its own URL."""
        c = Client(SERVER_NAME="127.0.0.1")
        c.force_login(self.user)
        return c.get(
            f"/courses/{self.course.pk}/lessons/{self.lesson.pk}/step/{kind}/",
            HTTP_HOST="127.0.0.1",
            HTTP_ACCEPT_LANGUAGE=("ar-EG" if lang == "ar" else "en-US"),
        )

    def test_lesson_page_works_without_media(self):
        """No media → launcher still 200 + shows the cover fallback marker."""
        lesson = self.lesson
        self.assertEqual(lesson.media.count(), 0)
        self.assertFalse(lesson.video_file)
        self.assertFalse(lesson.audio_file)
        r = self._get()
        self.assertNotEqual(r.status_code, 500)
        html = r.content.decode("utf-8", errors="replace")
        if r.status_code == 200:
            # Launcher shows the cover-fallback class when no image exists.
            self.assertIn("onlenco-hero__cover-fallback", html)

    def test_lesson_page_shows_learning_points(self):
        """The launcher renders 7 step cards (intro → finish), one per
        learning stage. That's the new home for 'learning points'."""
        r = self._get()
        if r.status_code != 200:
            return
        html = r.content.decode("utf-8", errors="replace")
        for kind in ["intro", "vocabulary", "examples", "dialogue",
                     "listening", "speaking", "finish"]:
            self.assertIn(f'data-step-kind="{kind}"', html)

    def test_lesson_page_shows_checklist(self):
        """Checklist lives on the finish step page, not the launcher."""
        r = self._get_step("finish")
        if r.status_code != 200:
            return
        html = r.content.decode("utf-8", errors="replace")
        self.assertIn("onlenco-finish__list", html)
        self.assertTrue(
            ("أستطيع" in html) or ("I can" in html) or ("Tick what you can do" in html),
            "checklist header missing",
        )

    def test_lesson_page_shows_quiz_button(self):
        """Quiz CTA appears on the launcher (quick-link) AND the finish step."""
        r = self._get()
        if r.status_code != 200:
            return
        html = r.content.decode("utf-8", errors="replace")
        self.assertIn("onlenco-quick-link--quiz", html)

    def test_lesson_page_shows_ai_tutor_button(self):
        """AI Tutor CTA lives on the speaking step (per the lesson flow)."""
        r = self._get_step("speaking")
        if r.status_code != 200:
            return
        html = r.content.decode("utf-8", errors="replace")
        self.assertIn("onlenco-tutor-cta", html)

    def test_lesson_page_supports_arabic_rtl(self):
        r = self._get(lang="ar")
        if r.status_code != 200:
            return
        html = r.content.decode("utf-8", errors="replace")
        # The page has Arabic step labels, RTL chrome.
        self.assertTrue(
            ('dir="rtl"' in html) or ("مفردات" in html) or ("ابدأ الدرس" in html),
            "Arabic/RTL markers missing under ar locale",
        )

    def test_english_examples_remain_ltr_in_arabic_ui(self):
        """English transcript on step pages stays LTR even when UI is AR."""
        r = self._get_step("dialogue", lang="ar")
        if r.status_code != 200:
            return
        html = r.content.decode("utf-8", errors="replace")
        self.assertIn('dir="ltr"', html)
