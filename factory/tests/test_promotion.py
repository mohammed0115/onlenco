from django.test import TestCase, override_settings

from factory.models import QuestionTemplate, SubstitutionBank, Topic
from factory.services import promotion_service
from learning_core.models import AdaptiveExercise


@override_settings(AI_API_KEY="", AI_LOCAL_API_BASE="")
class PromotionTests(TestCase):
    def setUp(self):
        SubstitutionBank.objects.create(
            name="subjects_singular", kind="subject", items=["she", "he"],
        )
        SubstitutionBank.objects.create(
            name="verbs_regular", kind="verb",
            items=[["walk", "walked", "walking"], ["play", "played", "playing"]],
        )
        topic = Topic.objects.create(
            name="ps", slug="grammar-a1-ps", kind="grammar", cefr_level="A1",
        )
        self.tpl = QuestionTemplate.objects.create(
            code="t-promo", name="t", topic=topic,
            question_type="multiple_choice", cefr_level="A1",
            pattern="{subject} ___ to school every day.",
            variables={"subject": "subjects_singular", "verb": "verbs_regular"},
            correct_answer_expression="verb.0 + 's'",
            distractor_strategy="morph",
            explanation_pattern="Use '{verb.0}s'.",
        )

    def test_promote_template_writes_items(self):
        before = AdaptiveExercise.objects.count()
        stats = promotion_service.promote_template(self.tpl, count=4)
        self.assertEqual(stats["candidates"], 4)
        self.assertGreaterEqual(stats["written"], 1)
        self.assertGreater(AdaptiveExercise.objects.count(), before)

    def test_promote_is_idempotent_via_dedup(self):
        # Run the same promotion twice — no extra rows on the second run.
        promotion_service.promote_template(self.tpl, count=4, start_variant=0)
        before = AdaptiveExercise.objects.count()
        stats = promotion_service.promote_template(self.tpl, count=4, start_variant=0)
        self.assertEqual(AdaptiveExercise.objects.count(), before)
        self.assertEqual(stats["written"], 0)
        # All 4 candidates should have been classified as duplicates.
        self.assertGreaterEqual(stats["duplicates"], 1)

    def test_quality_report_attached_to_metadata(self):
        promotion_service.promote_template(self.tpl, count=2)
        ex = AdaptiveExercise.objects.filter(metadata__template_code="t-promo").first()
        self.assertIsNotNone(ex)
        self.assertIn("quality_report", ex.metadata)
        self.assertIn("rule_score", ex.metadata["quality_report"])
