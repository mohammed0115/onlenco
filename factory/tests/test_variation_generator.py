from django.test import TestCase

from factory.models import QuestionTemplate, SubstitutionBank, Topic
from factory.services.variation_generator import (
    variations_for_topic,
    variations_for_topic_kind,
    virtual_capacity,
)


def _seed():
    SubstitutionBank.objects.create(
        name="subjects_singular", kind="subject", items=["she", "he", "the cat"],
    )
    SubstitutionBank.objects.create(
        name="verbs_regular", kind="verb",
        items=[["walk", "walked", "walking"], ["play", "played", "playing"]],
    )
    SubstitutionBank.objects.create(
        name="adj_pairs", kind="adjective_pair",
        items=[["tall", "taller", "tallest"], ["fast", "faster", "fastest"]],
    )
    t1 = Topic.objects.create(
        name="Present simple", slug="grammar-a1-ps",
        kind="grammar", cefr_level="A1",
    )
    t2 = Topic.objects.create(
        name="Comparatives", slug="grammar-a2-comp",
        kind="grammar", cefr_level="A2",
    )
    QuestionTemplate.objects.create(
        code="t-ps", name="ps", topic=t1, question_type="multiple_choice",
        cefr_level="A1",
        pattern="{subject} ___ to the office.",
        variables={"subject": "subjects_singular", "verb": "verbs_regular"},
        correct_answer_expression="verb.0 + 's'",
        distractor_strategy="morph",
    )
    QuestionTemplate.objects.create(
        code="t-comp", name="comp", topic=t2, question_type="multiple_choice",
        cefr_level="A2",
        pattern="My brother is ___ than me.",
        variables={"adj": "adj_pairs"},
        correct_answer_expression="adj.1",
        distractor_strategy="morph",
    )


class VariationGeneratorTests(TestCase):
    def setUp(self):
        _seed()

    def test_topic_variations_produces_count(self):
        items = variations_for_topic("grammar-a1-ps", count=5)
        self.assertEqual(len(items), 5)

    def test_topic_kind_variations_spreads_across_levels(self):
        items = variations_for_topic_kind("grammar", count=8)
        self.assertEqual(len(items), 8)
        levels = {i["cefr_level"] for i in items}
        # Both A1 and A2 templates should contribute.
        self.assertEqual(levels, {"A1", "A2"})

    def test_topic_kind_filtered_by_cefr(self):
        items = variations_for_topic_kind("grammar", cefr_level="A1", count=4)
        for i in items:
            self.assertEqual(i["cefr_level"], "A1")

    def test_virtual_capacity_aggregates_templates(self):
        # ps: 3×2 = 6,  comp: 2  →  total 8
        self.assertEqual(virtual_capacity(topic_kind="grammar"), 8)

    def test_variations_no_db_writes(self):
        """The whole point of variations: no AdaptiveExercise rows are persisted."""
        from learning_core.models import AdaptiveExercise
        before = AdaptiveExercise.objects.count()
        variations_for_topic("grammar-a1-ps", count=20)
        self.assertEqual(AdaptiveExercise.objects.count(), before)
