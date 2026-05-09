from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from exams import constants as C
from exams.models import Exam, ExamAttempt, ExamBlueprint, ExamQuestion
from exams.services.exam_scoring_service import grade_attempt, submit_answer
from learning_core.models import AdaptiveExercise, UserError

User = get_user_model()


@override_settings(AXES_ENABLED=False)
class ScoringTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="sc@x.com", email="sc@x.com", password="pw"
        )
        bp = ExamBlueprint.objects.create(
            name="bp", exam_type=C.EXAM_LESSON_QUIZ, cefr_level="A2",
            total_questions=2, duration_minutes=5, passing_score=60,
        )
        self.exam = Exam.objects.create(
            title="t", blueprint=bp, exam_type=C.EXAM_LESSON_QUIZ,
            cefr_level="A2", total_questions=2,
        )
        self.q1 = AdaptiveExercise.objects.create(
            cefr_level="A2", question_type="multiple_choice",
            question="2+2=?", correct_answer="4", options=["3", "4", "5", "6"],
            is_active=True, is_reviewed=True,
        )
        self.q2 = AdaptiveExercise.objects.create(
            cefr_level="A2", question_type="multiple_choice",
            question="capital of UK?", correct_answer="London",
            options=["Paris", "London", "Madrid", "Rome"],
            is_active=True, is_reviewed=True,
        )
        ExamQuestion.objects.create(exam=self.exam, question=self.q1, order=1)
        ExamQuestion.objects.create(exam=self.exam, question=self.q2, order=2)

    def test_correct_answer_scores_one_point(self):
        att = ExamAttempt.objects.create(user=self.user, exam=self.exam)
        ans = submit_answer(att, self.q1, "4")
        self.assertTrue(ans.is_correct)
        self.assertEqual(ans.score, 1)

    def test_wrong_answer_creates_user_error(self):
        att = ExamAttempt.objects.create(user=self.user, exam=self.exam)
        submit_answer(att, self.q1, "3")
        self.assertEqual(
            UserError.objects.filter(
                user=self.user,
                metadata__exam_attempt_id=att.id,
            ).count(),
            1,
        )

    def test_grade_attempt_finalises_with_percentage(self):
        att = ExamAttempt.objects.create(user=self.user, exam=self.exam)
        att = grade_attempt(att, [
            {"question_id": self.q1.id, "user_answer": "4"},      # correct
            {"question_id": self.q2.id, "user_answer": "Paris"},  # wrong
        ])
        self.assertEqual(att.status, "graded")
        self.assertAlmostEqual(att.percentage, 50.0)
        self.assertFalse(att.passed)

    def test_other_users_attempt_is_404_via_api(self):
        other = User.objects.create_user(
            username="other@x.com", email="other@x.com", password="pw"
        )
        att = ExamAttempt.objects.create(user=self.user, exam=self.exam)
        self.client.login(username="other@x.com", password="pw")
        resp = self.client.post(
            reverse("exams_api:submit", args=[att.id]),
            data={"answers": []},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 404)
