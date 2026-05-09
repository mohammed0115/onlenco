from django.contrib.auth import get_user_model
from django.test import TestCase

from exams import constants as C
from exams.models import ExamBlueprint
from exams.services.exam_assembly_service import assemble_exam
from learning_core.models import AdaptiveExercise

User = get_user_model()


class ExamAssemblyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="ass@x.com", email="ass@x.com", password="pw"
        )
        # Seed a small bank
        for diff, label in [(0.1, "easy"), (0.5, "medium"), (0.8, "hard")]:
            for i in range(5):
                AdaptiveExercise.objects.create(
                    cefr_level="A1", question_type="multiple_choice",
                    question=f"{label} #{i}", correct_answer="a",
                    options=["a", "b", "c", "d"],
                    difficulty_score=diff, is_active=True, is_reviewed=True,
                )
        self.bp = ExamBlueprint.objects.create(
            name="A1 mini",
            exam_type=C.EXAM_LESSON_QUIZ, cefr_level="A1",
            total_questions=5, duration_minutes=5, passing_score=70,
            difficulty_distribution={"easy": 0.4, "medium": 0.4, "hard": 0.2},
            question_type_distribution={"multiple_choice": 1.0},
        )

    def test_assemble_returns_exam_with_n_questions(self):
        exam = assemble_exam(blueprint=self.bp, user=self.user)
        self.assertEqual(exam.questions.count(), 5)
        self.assertEqual(exam.cefr_level, "A1")

    def test_adaptive_assembly_does_not_crash(self):
        exam = assemble_exam(blueprint=self.bp, user=self.user, adaptive=True)
        self.assertEqual(exam.questions.count(), 5)
        self.assertTrue(exam.is_adaptive)

    def test_unknown_blueprint_raises(self):
        with self.assertRaises(ValueError):
            assemble_exam(exam_type="nope", cefr_level="A1")
