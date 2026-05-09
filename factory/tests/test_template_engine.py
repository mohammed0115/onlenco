from django.test import TestCase

from factory.models import QuestionTemplate, SubstitutionBank, Topic
from factory.services.template_engine import (
    deterministic_seed,
    evaluate_expression,
    maximum_variations,
    render_many,
    render_one,
    render_pattern,
)


def _seed_a1_present_simple() -> QuestionTemplate:
    SubstitutionBank.objects.create(
        name="subjects_singular", kind="subject",
        items=["she", "he", "the cat"],
    )
    SubstitutionBank.objects.create(
        name="verbs_regular", kind="verb",
        items=[["walk", "walked", "walking"], ["play", "played", "playing"]],
    )
    topic = Topic.objects.create(
        name="Present simple", slug="grammar-a1-present-simple",
        kind="grammar", cefr_level="A1",
    )
    return QuestionTemplate.objects.create(
        code="t-presimple", name="Present simple — 3sg",
        topic=topic, question_type="multiple_choice", cefr_level="A1",
        pattern="{subject} ___ to the office every day.",
        variables={"subject": "subjects_singular", "verb": "verbs_regular"},
        correct_answer_expression="verb.0 + 's'",
        distractor_strategy="morph",
        explanation_pattern="Use '{verb.0}s' with '{subject}'.",
    )


class DSLTests(TestCase):
    def test_render_pattern_substitutes_simple(self):
        out = render_pattern("Hi {name}!", {"name": "Sara"})
        self.assertEqual(out, "Hi Sara!")

    def test_render_pattern_indexes_tuple(self):
        out = render_pattern("Past of {v.0} is {v.1}.", {"v": ["go", "went"]})
        self.assertEqual(out, "Past of go is went.")

    def test_evaluate_expression_concat(self):
        out = evaluate_expression("verb.0 + 's'", {"verb": ["walk", "walked"]})
        self.assertEqual(out, "walks")

    def test_evaluate_expression_literal_only(self):
        self.assertEqual(evaluate_expression("'hello'", {}), "hello")


class RenderTests(TestCase):
    def setUp(self):
        self.tpl = _seed_a1_present_simple()

    def test_render_one_is_deterministic(self):
        a = render_one(self.tpl, variant=42)
        b = render_one(self.tpl, variant=42)
        self.assertEqual(a["question"], b["question"])
        self.assertEqual(a["correct_answer"], b["correct_answer"])

    def test_render_one_changes_with_variant(self):
        # Across many variants we should see at least 2 distinct surface forms.
        seen = {render_one(self.tpl, variant=v)["question"] for v in range(10)}
        self.assertGreater(len(seen), 1)

    def test_render_one_correct_in_options(self):
        item = render_one(self.tpl, variant=0)
        self.assertIn(item["correct_answer"], item["options"])
        self.assertGreaterEqual(len(item["options"]), 2)

    def test_render_many_returns_count(self):
        items = render_many(self.tpl, count=5)
        self.assertEqual(len(items), 5)
        codes = {it["code"] for it in items}
        self.assertEqual(len(codes), 5)

    def test_maximum_variations_product(self):
        # 3 subjects × 2 verbs = 6 combinations
        self.assertEqual(maximum_variations(self.tpl), 6)

    def test_deterministic_seed_stable(self):
        self.assertEqual(deterministic_seed("x", 1), deterministic_seed("x", 1))
        self.assertNotEqual(deterministic_seed("x", 1), deterministic_seed("x", 2))
