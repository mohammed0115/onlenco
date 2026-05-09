from django.test import TestCase

from question_factory import constants as C
from question_factory.models import QuestionBlueprint
from question_factory.services import blueprint_service


class BlueprintServiceTests(TestCase):
    def setUp(self):
        QuestionBlueprint.objects.create(
            code="bp-A1-grammar-1", title="t1", cefr_level="A1",
            skill=C.SKILL_GRAMMAR, question_type="multiple_choice",
            template_pattern="x ___", expected_answer_pattern="'a'",
        )
        QuestionBlueprint.objects.create(
            code="bp-A1-vocab-1", title="t2", cefr_level="A1",
            skill=C.SKILL_VOCABULARY, question_type="fill_blank",
            template_pattern="y ___", expected_answer_pattern="'b'",
            generation_strategy=C.GEN_HYBRID,
        )
        QuestionBlueprint.objects.create(
            code="bp-A2-grammar-1", title="t3", cefr_level="A2",
            skill=C.SKILL_GRAMMAR, question_type="multiple_choice",
            template_pattern="z ___", expected_answer_pattern="'c'",
            is_active=False,
        )

    def test_filter_by_level(self):
        qs = blueprint_service.filter_blueprints(cefr_level="A1")
        self.assertEqual(qs.count(), 2)

    def test_filter_by_strategy(self):
        qs = blueprint_service.filter_blueprints(strategy=C.GEN_HYBRID)
        self.assertEqual(qs.count(), 1)

    def test_filter_active_only_by_default(self):
        qs = blueprint_service.filter_blueprints()
        # The A2 inactive row is excluded by default.
        codes = {b.code for b in qs}
        self.assertNotIn("bp-A2-grammar-1", codes)

    def test_get_by_code(self):
        bp = blueprint_service.get_by_code("bp-A1-grammar-1")
        self.assertEqual(bp.title, "t1")

    def test_by_signature(self):
        bp = blueprint_service.by_signature(
            cefr_level="A1", skill=C.SKILL_VOCABULARY,
            question_type="fill_blank",
        )
        self.assertEqual(bp.code, "bp-A1-vocab-1")

    def test_upsert_creates_then_updates(self):
        bp = blueprint_service.upsert(
            code="bp-new", title="x", cefr_level="A0",
            skill=C.SKILL_GRAMMAR, question_type="multiple_choice",
            template_pattern="p", expected_answer_pattern="'a'",
        )
        self.assertEqual(bp.title, "x")
        bp2 = blueprint_service.upsert(
            code="bp-new", title="updated", cefr_level="A0",
            skill=C.SKILL_GRAMMAR, question_type="multiple_choice",
            template_pattern="p", expected_answer_pattern="'a'",
        )
        self.assertEqual(bp.id, bp2.id)
        self.assertEqual(bp2.title, "updated")

    def test_stats_buckets(self):
        s = blueprint_service.stats()
        self.assertEqual(s["total"], 2)  # only active rows
        self.assertEqual(s["by_cefr"].get("A1"), 2)
