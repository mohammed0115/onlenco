from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from learning_core.models import AdaptiveExercise, WeeklyAssessment

User = get_user_model()


class WeeklyAssessmentViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="wv", password="pw")
        self.client.force_login(self.user)
        self.assessment = WeeklyAssessment.objects.create(
            user=self.user, triggered_after_lessons_count=3, status="pending"
        )
        self.ex1 = AdaptiveExercise.objects.create(
            cefr_level="A2",
            difficulty_score=0.4,
            question_type="multiple_choice",
            question="She ___ to school every day.",
            options=["go", "goes"],
            correct_answer="goes",
        )
        self.ex2 = AdaptiveExercise.objects.create(
            cefr_level="A2",
            difficulty_score=0.4,
            question_type="fill_blank",
            question="Yesterday I ___ (eat) breakfast.",
            options=[],
            correct_answer="ate",
        )
        self.assessment.exercises.set([self.ex1, self.ex2])

    def test_get_renders_questions_and_marks_in_progress(self):
        r = self.client.get(reverse("weekly_assessment", args=[self.assessment.id]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "She ___ to school every day.")
        self.assertContains(r, "Yesterday I ___")
        self.assessment.refresh_from_db()
        self.assertEqual(self.assessment.status, "in_progress")

    def test_post_grades_and_completes(self):
        r = self.client.post(
            reverse("weekly_assessment", args=[self.assessment.id]),
            data={f"ex_{self.ex1.id}": "goes", f"ex_{self.ex2.id}": "ate"},
        )
        self.assertEqual(r.status_code, 200)
        self.assessment.refresh_from_db()
        self.assertEqual(self.assessment.status, "completed")
        self.assertEqual(self.assessment.score, 100.0)

    def test_other_users_assessment_404(self):
        other = User.objects.create_user(username="other", password="pw")
        self.client.force_login(other)
        r = self.client.get(reverse("weekly_assessment", args=[self.assessment.id]))
        self.assertEqual(r.status_code, 404)
