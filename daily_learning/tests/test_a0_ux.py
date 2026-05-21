from django.test import TestCase
from django.urls import reverse

from daily_learning.services.daily_plan_generator import generate_for_user

from .factories import make_student


class A0DailyLearningUXTests(TestCase):
    def test_daily_plan_renders_a0_journey_frame(self):
        user = make_student(
            username="a0_daily_ui",
            cefr_level="A0",
            language="ar",
            onboarding_path="beginner_start",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("daily_learning:daily_plan"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-testid="a0-daily-journey"')
        self.assertContains(response, "رحلة البداية من الصفر اليوم")
        self.assertContains(response, "جملة قصيرة")
        self.assertNotContains(response, "Grammar tip")

    def test_a0_generated_content_avoids_complex_terms(self):
        user = make_student(
            username="a0_terms",
            cefr_level="A0",
            language="ar",
            onboarding_path="beginner_start",
        )

        plan = generate_for_user(user)

        banned = (
            "grammar", "tense", "verb", "pronoun", "adjective", "singular",
            "قواعد", "تصريف", "ضمير", "صفة", "مفرد",
        )
        for item in plan.items.all():
            combined = " ".join([
                item.title or "",
                item.instructions or "",
                item.content_text or "",
                item.question or "",
                item.explanation or "",
            ]).lower()
            for term in banned:
                self.assertNotIn(term, combined, f"{term!r} leaked in item {item.id}")

    def test_a0_daily_plan_has_arabic_explanation(self):
        user = make_student(
            username="a0_arabic_explain",
            cefr_level="A0",
            language="ar",
            onboarding_path="beginner_start",
        )

        plan = generate_for_user(user)

        self.assertTrue(
            any(
                any("\u0600" <= ch <= "\u06ff" for ch in (item.instructions + item.explanation))
                for item in plan.items.all()
            ),
            "A0 Arabic learner should receive Arabic instructions or explanations.",
        )
