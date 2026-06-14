import re
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from courses.models import Course, CourseLevel, CourseLessonProgress, Lesson


User = get_user_model()


class A0WorldCoursePageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="a0world", password="pw")
        self.user.profile.cefr_level = "A0"
        self.user.profile.preferred_language = "ar"
        self.user.profile.onboarding_path = "beginner_start"
        self.user.profile.onboarding_completed = True
        self.user.profile.save()
        self.client.force_login(self.user)

        self.level = CourseLevel.objects.create(
            code="A0",
            name="A0",
            order=0,
            is_active=True,
        )
        self.course = Course.objects.create(
            title="A0 World",
            title_ar="عالم A0",
            slug="a0-world",
            level=self.level,
            status="published",
            is_active=True,
            is_free=True,
        )
        self.lesson_one = Lesson.objects.create(
            course=self.course,
            title="Letters",
            title_ar="الحروف",
            order=1,
            status="published",
            is_active=True,
            cefr_level="A0",
            content_ar="اسمع وكرر.",
        )
        self.lesson_two = Lesson.objects.create(
            course=self.course,
            title="Hello",
            title_ar="مرحبا",
            order=2,
            status="published",
            is_active=True,
            cefr_level="A0",
            content_ar="قل مرحبا.",
        )

    def _page(self) -> str:
        response = self.client.get(reverse("courses:course_detail", args=[self.course.pk]))
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def _mission_state(self, html: str, index: int) -> str:
        match = re.search(
            rf'data-mission-index="{index}"\s+data-state="([^"]+)"',
            html,
            re.S,
        )
        self.assertIsNotNone(match, f"mission {index} state not found")
        return match.group(1)

    def test_a0_page_has_beginner_message(self):
        html = self._page()
        self.assertIn("أنت تبدأ من الصفر. سنمشي معك خطوة بخطوة.", html)

    def test_a0_map_shows_missions(self):
        html = self._page()
        self.assertIn('data-testid="a0-mission-map"', html)
        self.assertIn("بوابة الحروف", html)
        self.assertIn("مدينة التحيات", html)
        self.assertEqual(html.count('data-testid="a0-mission"'), 9)

    def test_first_mission_unlocked_and_later_missions_locked(self):
        html = self._page()
        self.assertEqual(self._mission_state(html, 1), "unlocked")
        self.assertEqual(self._mission_state(html, 2), "locked")
        self.assertEqual(self._mission_state(html, 9), "locked")

    def test_completion_unlocks_next_mission(self):
        # Completed a day ago — the daily-drip gate has elapsed, so the
        # next mission is now open.
        CourseLessonProgress.objects.create(
            user=self.user,
            lesson=self.lesson_one,
            video_completed=True,
            completed_at=timezone.now() - timedelta(days=1),
        )

        html = self._page()

        self.assertEqual(self._mission_state(html, 1), "completed")
        self.assertEqual(self._mission_state(html, 2), "unlocked")

    def test_completing_a_mission_unlocks_the_next_immediately(self):
        # Unlock-on-completion: finishing a lesson opens the next one right
        # away (no calendar-day wait).
        CourseLessonProgress.objects.create(
            user=self.user,
            lesson=self.lesson_one,
            video_completed=True,
            completed_at=timezone.now(),
        )

        html = self._page()

        self.assertEqual(self._mission_state(html, 1), "completed")
        self.assertEqual(self._mission_state(html, 2), "unlocked")

    def test_a0_page_avoids_complex_grammar_terms(self):
        html = self._page().lower()
        for banned in ("grammar", "tense", "verb", "pronoun", "قواعد", "تصريف", "ضمير"):
            self.assertNotIn(banned, html)

    def test_a0_page_has_arabic_explanation(self):
        html = self._page()
        self.assertIn("مسار ممتع لطالب لا يعرف الإنجليزية بعد.", html)
        self.assertIn("كلمة", html)
        self.assertIn("صوت", html)
