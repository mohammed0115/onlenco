from django.contrib.auth import get_user_model
from django.test import TestCase

from learning_core.models import (
    AdaptiveExercise,
    ExerciseAttempt,
    Skill,
    UserError,
    UserWeakness,
)
from lessons.models import Lesson, Question, Quiz
from lessons.services.adaptive_quiz_adapter import process_quiz_submission

User = get_user_model()


class AdaptiveQuizAdapterTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ria", password="pw")
        self.lesson = Lesson.objects.create(
            title="A2 Reading L1", skill="reading", level="A2", duration_minutes=10
        )
        self.quiz = Quiz.objects.create(lesson=self.lesson, pass_score=60)
        self.q1 = Question.objects.create(
            quiz=self.quiz,
            prompt="Pick the correct option",
            choice_a="goes",
            choice_b="go",
            correct="a",
        )
        self.q2 = Question.objects.create(
            quiz=self.quiz,
            prompt="Pick the past form",
            choice_a="went",
            choice_b="goed",
            correct="a",
        )
        # Skill row for "reading" so adapter can attach to it
        self.skill = Skill.objects.create(
            name="Reading core", category="reading", cefr_level="A2"
        )

    def test_correct_answers_record_attempts_no_errors(self):
        results = [
            {"q": self.q1, "chosen": "a", "correct": "a"},
            {"q": self.q2, "chosen": "a", "correct": "a"},
        ]
        summary = process_quiz_submission(self.user, self.lesson, results)
        self.assertEqual(summary["attempts_recorded"], 2)
        self.assertEqual(summary["errors_created"], 0)
        self.assertFalse(UserError.objects.filter(user=self.user).exists())
        self.assertEqual(ExerciseAttempt.objects.filter(user=self.user).count(), 2)
        # Mirror exercises created and reused
        self.assertEqual(AdaptiveExercise.objects.count(), 2)

    def test_wrong_answer_creates_user_error_and_weakness(self):
        results = [
            {"q": self.q1, "chosen": "b", "correct": "a"},
            {"q": self.q2, "chosen": "b", "correct": "a"},
        ]
        summary = process_quiz_submission(self.user, self.lesson, results)
        self.assertEqual(summary["errors_created"], 2)
        self.assertTrue(summary["weaknesses_recomputed"])
        errs = UserError.objects.filter(user=self.user)
        self.assertEqual(errs.count(), 2)
        self.assertEqual(errs.first().source_type, "quiz")
        self.assertEqual(errs.first().skill, self.skill)
        # Weakness exists for this skill
        self.assertTrue(UserWeakness.objects.filter(user=self.user, skill=self.skill).exists())

    def test_mirror_reused_on_resubmission(self):
        results = [{"q": self.q1, "chosen": "a", "correct": "a"}]
        process_quiz_submission(self.user, self.lesson, results)
        process_quiz_submission(self.user, self.lesson, results)
        # Same Question → same AdaptiveExercise mirror
        self.assertEqual(AdaptiveExercise.objects.count(), 1)
        self.assertEqual(ExerciseAttempt.objects.count(), 2)

    def test_lesson_progress_unaffected_by_adapter_failure(self):
        # If we pass garbage, adapter should swallow the error.
        bad_results = [{"q": None, "chosen": "a", "correct": "a"}]
        summary = process_quiz_submission(self.user, self.lesson, bad_results)
        # No crash; no rows persisted
        self.assertEqual(summary["attempts_recorded"], 0)
