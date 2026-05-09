"""Verify the motivation engine is invoked from key user-facing paths."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from learning_core.models import Skill
from lessons.models import Lesson, Quiz, Question
from lessons.services.adaptive_quiz_adapter import process_quiz_submission
from motivation.models import LearnerActivitySnapshot, UserXP

User = get_user_model()


class QuizMotivationHookTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="hook@x.com", email="hook@x.com", password="pw"
        )
        self.skill = Skill.objects.create(name="reading", category="reading")
        self.lesson = Lesson.objects.create(
            title="Test", skill="reading", level="A2", sort_order=1,
        )
        self.quiz = Quiz.objects.create(lesson=self.lesson, pass_score=70)
        self.q = Question.objects.create(
            quiz=self.quiz, prompt="Pick a", choice_a="x", choice_b="y", correct="a",
        )

    def test_quiz_submission_runs_motivation_engine(self):
        results = [{"q": self.q, "chosen": "a", "correct": "a"}]
        process_quiz_submission(self.user, self.lesson, results)
        # Motivation side effect: a snapshot row + UserXP row both exist.
        self.assertTrue(
            LearnerActivitySnapshot.objects.filter(user=self.user).exists(),
            "motivation engine did not create a snapshot",
        )
        self.assertTrue(
            UserXP.objects.filter(user=self.user).exists(),
            "motivation engine did not create a UserXP row",
        )
