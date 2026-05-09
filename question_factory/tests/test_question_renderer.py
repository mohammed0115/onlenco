from django.test import TestCase

from question_factory.models import QuestionBlueprint
from question_factory.services.question_renderer import (
    evaluate_expression, render, render_pattern,
)


class RenderPatternTests(TestCase):
    def test_substitutes_simple_var(self):
        self.assertEqual(render_pattern("Hi {x}!", {"x": "Sara"}), "Hi Sara!")

    def test_indexes_tuple(self):
        self.assertEqual(
            render_pattern("Past of {v.0} is {v.1}.", {"v": ["go", "went"]}),
            "Past of go is went.",
        )

    def test_lower_accessor(self):
        self.assertEqual(render_pattern("{x.lower}", {"x": "ABC"}), "abc")


class EvaluateExpressionTests(TestCase):
    def test_concat_with_literal(self):
        self.assertEqual(
            evaluate_expression("v.0 + 's'", {"v": ["walk"]}),
            "walks",
        )

    def test_pure_literal(self):
        self.assertEqual(evaluate_expression("'open response'", {}), "open response")


class RenderBlueprintTests(TestCase):
    def setUp(self):
        self.bp = QuestionBlueprint.objects.create(
            code="t-render", title="t",
            cefr_level="A1", skill="grammar",
            question_type="multiple_choice",
            template_pattern="{subject} ___ to school every day.",
            expected_answer_pattern="verb.0 + 's'",
            explanation_pattern="Use '{verb.0}s' with '{subject}'.",
            variables_schema={
                "subject": ["she", "he"],
                "verb": [["walk", "walked"], ["play", "played"]],
            },
            metadata={"distractor_config": {"strategy": "morph"}},
        )

    def test_render_produces_dict_with_required_fields(self):
        item = render(self.bp, {"subject": "she", "verb": ["walk", "walked"]})
        self.assertEqual(item["question_text"], "she ___ to school every day.")
        self.assertEqual(item["correct_answer"], "walks")
        self.assertIn("walks", item["options"])
        self.assertEqual(item["cefr_level"], "A1")
        self.assertEqual(item["skill"], "grammar")
        self.assertTrue(item["content_hash"])

    def test_render_is_deterministic(self):
        a = render(self.bp, {"subject": "he", "verb": ["play", "played"]}, variant=7)
        b = render(self.bp, {"subject": "he", "verb": ["play", "played"]}, variant=7)
        self.assertEqual(a, b)

    def test_render_distractors_morph_excludes_correct(self):
        item = render(self.bp, {"subject": "she", "verb": ["walk", "walked"]})
        self.assertNotIn(item["correct_answer"], [d for d in item["options"]
                                                   if d != item["correct_answer"]])

    def test_render_metadata_includes_blueprint_code(self):
        item = render(self.bp, {"subject": "she", "verb": ["walk", "walked"]})
        self.assertEqual(item["metadata"]["blueprint_code"], "t-render")
