from django.db import IntegrityError
from django.test import TestCase

from question_factory import constants as C
from question_factory.models import (
    GeneratedQuestion, GenerationBatch, QuestionBlueprint, QuestionVariableSet,
)


class QuestionFactoryModelTests(TestCase):
    def test_blueprint_code_unique(self):
        QuestionBlueprint.objects.create(
            code="x1", title="t", question_type="multiple_choice",
            template_pattern="x ___", expected_answer_pattern="'a'",
        )
        with self.assertRaises(IntegrityError):
            QuestionBlueprint.objects.create(
                code="x1", title="dup", question_type="multiple_choice",
                template_pattern="y", expected_answer_pattern="'b'",
            )

    def test_generated_question_code_unique(self):
        GeneratedQuestion.objects.create(
            code="qf-1", question_type="multiple_choice",
            question_text="x", correct_answer="a", content_hash="h1",
        )
        with self.assertRaises(IntegrityError):
            GeneratedQuestion.objects.create(
                code="qf-1", question_type="multiple_choice",
                question_text="dup", correct_answer="b", content_hash="h2",
            )

    def test_generation_batch_status_default(self):
        b = GenerationBatch.objects.create(batch_id="b1", target_count=10)
        self.assertEqual(b.status, C.BATCH_PENDING)

    def test_variable_set_belongs_to_blueprint(self):
        bp = QuestionBlueprint.objects.create(
            code="vs-host", title="t", question_type="multiple_choice",
            template_pattern="{a}", expected_answer_pattern="a",
        )
        vs = QuestionVariableSet.objects.create(
            blueprint=bp, variables={"a": ["x", "y"]},
        )
        self.assertEqual(bp.variable_sets.count(), 1)
        self.assertEqual(vs.blueprint_id, bp.id)
