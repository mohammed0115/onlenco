from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase

from exams import constants as C
from exams.models import (
    Exam,
    ExamAnswer,
    ExamAttempt,
    ExamBlueprint,
    ExamQuestion,
    QuestionGenerationBatch,
)
from learning_core.models import AdaptiveExercise

User = get_user_model()


class ExamModelTests(TestCase):
    def test_blueprint_signature_unique(self):
        ExamBlueprint.objects.create(
            name="x", exam_type=C.EXAM_PLACEMENT, cefr_level="A1",
            total_questions=10, duration_minutes=10,
        )
        with self.assertRaises(IntegrityError):
            ExamBlueprint.objects.create(
                name="dup", exam_type=C.EXAM_PLACEMENT, cefr_level="A1",
            )

    def test_examquestion_unique_question_per_exam(self):
        bp = ExamBlueprint.objects.create(
            name="b", exam_type=C.EXAM_LESSON_QUIZ, cefr_level="A2",
        )
        ex = Exam.objects.create(
            title="t", blueprint=bp, exam_type=C.EXAM_LESSON_QUIZ,
            cefr_level="A2", total_questions=2, duration_minutes=5,
        )
        q = AdaptiveExercise.objects.create(
            cefr_level="A2", question_type="multiple_choice",
            question="?", correct_answer="a",
        )
        ExamQuestion.objects.create(exam=ex, question=q, order=1)
        with self.assertRaises(IntegrityError):
            ExamQuestion.objects.create(exam=ex, question=q, order=2)

    def test_examanswer_unique_per_attempt(self):
        bp = ExamBlueprint.objects.create(
            name="b2", exam_type=C.EXAM_LESSON_QUIZ, cefr_level="A2",
        )
        ex = Exam.objects.create(title="t2", blueprint=bp,
                                 exam_type=C.EXAM_LESSON_QUIZ, cefr_level="A2")
        u = User.objects.create_user(username="u@x.com", email="u@x.com", password="pw")
        att = ExamAttempt.objects.create(user=u, exam=ex)
        q = AdaptiveExercise.objects.create(
            cefr_level="A2", question_type="multiple_choice",
            question="q", correct_answer="a",
        )
        ExamAnswer.objects.create(attempt=att, question=q, user_answer="a", is_correct=True)
        with self.assertRaises(IntegrityError):
            ExamAnswer.objects.create(attempt=att, question=q, user_answer="b")

    def test_batch_status_default(self):
        b = QuestionGenerationBatch.objects.create(batch_id="b1", target_count=10)
        self.assertEqual(b.status, C.BATCH_PENDING)
