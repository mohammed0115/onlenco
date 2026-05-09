"""Tests for the `backfill_taxonomy` management command + the
forward-looking FK lookups in the template generator."""
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from learning_core.models import AdaptiveExercise, GrammarTopic, Skill
from question_factory.models import QuestionBlueprint


class BackfillTaxonomyTests(TestCase):
    def test_seeds_skill_and_grammar_topic_rows(self):
        self.assertEqual(Skill.objects.count(), 0)
        self.assertEqual(GrammarTopic.objects.count(), 0)

        call_command("backfill_taxonomy", stdout=StringIO())

        # 8 categories, one Skill row each
        self.assertEqual(Skill.objects.count(), 8)
        # ≥ 18 canonical topics seeded
        self.assertGreaterEqual(GrammarTopic.objects.count(), 18)

    def test_idempotent(self):
        call_command("backfill_taxonomy", stdout=StringIO())
        n_skills = Skill.objects.count()
        n_topics = GrammarTopic.objects.count()
        call_command("backfill_taxonomy", stdout=StringIO())
        self.assertEqual(Skill.objects.count(), n_skills)
        self.assertEqual(GrammarTopic.objects.count(), n_topics)

    def test_links_blueprint_grammar_topic_from_code(self):
        bp = QuestionBlueprint.objects.create(
            code="qf-gram-A1-presimple-3sg", title="t",
            cefr_level="A1", skill="grammar",
            question_type="multiple_choice",
            template_pattern="{x} ___", expected_answer_pattern="'a'",
        )
        self.assertIsNone(bp.grammar_topic_id)
        call_command("backfill_taxonomy", stdout=StringIO())
        bp.refresh_from_db()
        self.assertIsNotNone(bp.grammar_topic_id)
        self.assertEqual(bp.grammar_topic.slug, "present-simple")

    def test_links_adaptive_exercise_skill_and_topic_from_metadata(self):
        # Items mimicking what the factory bulk pipeline writes.
        AdaptiveExercise.objects.create(
            cefr_level="A1", question_type="multiple_choice",
            question="dummy", correct_answer="a",
            metadata={"bank_code": "tpl:A1:grammar:psimple:she:walk"},
        )
        AdaptiveExercise.objects.create(
            cefr_level="A2", question_type="multiple_choice",
            question="dummy 2", correct_answer="b",
            metadata={"template_code": "tpl-grammar-A2-articles"},
        )

        call_command("backfill_taxonomy", stdout=StringIO())

        e1 = AdaptiveExercise.objects.get(question="dummy")
        e2 = AdaptiveExercise.objects.get(question="dummy 2")
        self.assertIsNotNone(e1.skill_id)
        self.assertEqual(e1.skill.category, "grammar")
        self.assertIsNotNone(e1.topic_id)
        self.assertEqual(e1.topic.slug, "present-simple")

        self.assertIsNotNone(e2.skill_id)
        self.assertEqual(e2.skill.category, "grammar")
        self.assertEqual(e2.topic.slug, "articles")

    def test_blueprint_only_flag_skips_adaptive_exercise_pass(self):
        AdaptiveExercise.objects.create(
            cefr_level="A1", question_type="multiple_choice",
            question="hi", correct_answer="a",
            metadata={"bank_code": "tpl:A1:grammar:psimple:she:walk"},
        )
        call_command("backfill_taxonomy", "--blueprints-only", stdout=StringIO())
        # AE row was *not* updated
        ex = AdaptiveExercise.objects.get(question="hi")
        self.assertIsNone(ex.skill_id)
        self.assertIsNone(ex.topic_id)


class TemplateGeneratorFKLookupTests(TestCase):
    """The forward-looking change: `_skill_id_for` + `_topic_id_for`
    return the right ids when the taxonomy is seeded."""

    def setUp(self):
        # Seed the taxonomy so the lookups succeed.
        call_command("backfill_taxonomy", "--blueprints-only", stdout=StringIO())
        # Force the cache to re-load against the seeded rows.
        from exams.services import template_question_generator as tg
        tg._SKILL_FK_CACHE.clear()
        tg._TOPIC_FK_CACHE.clear()

    def test_skill_lookup_returns_canonical_skill_id(self):
        from exams.services.template_question_generator import _skill_id_for
        sid = _skill_id_for("grammar")
        self.assertIsNotNone(sid)
        self.assertEqual(Skill.objects.get(pk=sid).category, "grammar")

    def test_topic_lookup_handles_underscore_aliases(self):
        from exams.services.template_question_generator import _topic_id_for
        # `present_simple` (factory's metadata format) → "present-simple" topic
        tid = _topic_id_for("present_simple")
        self.assertIsNotNone(tid)
        self.assertEqual(GrammarTopic.objects.get(pk=tid).slug, "present-simple")

    def test_topic_alias_maps_synonyms(self):
        from exams.services.template_question_generator import _topic_id_for
        # `vocab_inference` (factory metadata) → "vocab-in-context" topic
        tid = _topic_id_for("vocab_inference")
        self.assertIsNotNone(tid)
        self.assertEqual(GrammarTopic.objects.get(pk=tid).slug, "vocab-in-context")

    def test_unknown_topic_returns_none_without_raising(self):
        from exams.services.template_question_generator import _topic_id_for
        self.assertIsNone(_topic_id_for("not-a-real-topic"))
