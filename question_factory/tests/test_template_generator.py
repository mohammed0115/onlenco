from django.test import TestCase

from question_factory import constants as C
from question_factory.models import (
    GeneratedQuestion, GenerationBatch, QuestionBlueprint,
)
from question_factory.services import template_generator


def _seed_blueprint() -> QuestionBlueprint:
    return QuestionBlueprint.objects.create(
        code="t-tg", title="t",
        cefr_level="A1", skill=C.SKILL_GRAMMAR,
        question_type="multiple_choice",
        template_pattern="{subject} ___ to school every day.",
        expected_answer_pattern="verb.0 + 's'",
        explanation_pattern="Use '{verb.0}s' with '{subject}'.",
        variables_schema={
            "subject": ["she", "he", "the cat"],
            "verb": [["walk", "walked"], ["play", "played"]],
        },
        metadata={"distractor_config": {"strategy": "morph"}},
    )


class TemplateGeneratorTests(TestCase):
    def test_render_for_blueprint_yields_count(self):
        bp = _seed_blueprint()
        items = template_generator.render_for_blueprint(bp, count=5)
        self.assertEqual(len(items), 5)
        for it in items:
            self.assertEqual(it["cefr_level"], "A1")
            self.assertTrue(it["question_text"])
            self.assertIn(it["correct_answer"], it["options"])

    def test_generate_for_blueprint_persists(self):
        bp = _seed_blueprint()
        before = GeneratedQuestion.objects.count()
        stats = template_generator.generate_for_blueprint(bp, count=4)
        self.assertGreater(stats["accepted"], 0)
        self.assertGreater(GeneratedQuestion.objects.count(), before)

    def test_generate_is_idempotent_via_dedup(self):
        bp = _seed_blueprint()
        template_generator.generate_for_blueprint(bp, count=4, start_variant=0)
        before = GeneratedQuestion.objects.count()
        stats = template_generator.generate_for_blueprint(bp, count=4, start_variant=0)
        # All 4 candidates are duplicates the second time.
        self.assertEqual(stats["accepted"], 0)
        self.assertEqual(GeneratedQuestion.objects.count(), before)

    def test_generate_to_target_creates_batch(self):
        _seed_blueprint()
        before = GenerationBatch.objects.count()
        batch = template_generator.generate_to_target(target_count=4)
        self.assertEqual(GenerationBatch.objects.count(), before + 1)
        self.assertEqual(batch.status, C.BATCH_COMPLETED)
        self.assertGreater(batch.accepted_count, 0)

    def test_generate_to_target_fails_when_no_blueprints(self):
        batch = template_generator.generate_to_target(
            target_count=10, cefr_level="C2", skill=C.SKILL_PRONUNCIATION,
        )
        self.assertEqual(batch.status, C.BATCH_FAILED)
        self.assertIn("No active template blueprints", batch.error_message)
