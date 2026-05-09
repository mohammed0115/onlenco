"""Tests for the RAG retrieval layer.

Each test seeds a tiny, realistic corpus through the actual ORM models
(no mocking) so a regression in filter wiring is caught."""
from django.test import TestCase

from ai_engine.services import (
    context_builder,
    example_retriever,
    question_retriever,
    retrieval_service,
)
from ai_training.models import AITrainingExample
from learning_core.models import AdaptiveExercise, GrammarTopic, Skill
from question_factory.models import GeneratedQuestion


def _ex(question, *, cefr="A1", skill_obj=None, topic_obj=None,
        is_active=True, is_reviewed=True, qtype="multiple_choice",
        quality=85, difficulty=0.4, explanation="Default explanation."):
    return AdaptiveExercise.objects.create(
        cefr_level=cefr, question_type=qtype, question=question,
        correct_answer="goes",
        options=["go", "goes", "going", "gone"],
        explanation=explanation,
        difficulty_score=difficulty, quality_score=quality,
        is_active=is_active, is_reviewed=is_reviewed,
        skill=skill_obj, topic=topic_obj,
    )


class QuestionRetrieverFilterTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.skill_grammar = Skill.objects.create(
            name="Grammar A1", category="grammar", cefr_level="A1",
        )
        cls.skill_vocab = Skill.objects.create(
            name="Vocab A1", category="vocabulary", cefr_level="A1",
        )
        cls.topic_present_simple = GrammarTopic.objects.create(
            name="Present simple", slug="present-simple", cefr_level="A1",
        )
        cls.topic_articles = GrammarTopic.objects.create(
            name="Articles", slug="articles", cefr_level="A1",
        )
        # 3 A1 grammar items on present_simple
        for i in range(3):
            _ex(f"She walks home #{i}.",
                skill_obj=cls.skill_grammar, topic_obj=cls.topic_present_simple)
        # 2 A2 grammar items
        for i in range(2):
            _ex(f"They walked home #{i}.", cefr="A2",
                skill_obj=cls.skill_grammar, topic_obj=cls.topic_present_simple)
        # 1 A1 vocab item
        _ex("What does 'happy' mean?",
            skill_obj=cls.skill_vocab, qtype="multiple_choice")
        # 1 A1 grammar item on a different topic (articles)
        _ex("I have ___ apple.",
            skill_obj=cls.skill_grammar, topic_obj=cls.topic_articles)

    # ---- spec test 1: retrieve by CEFR --------------------------------

    def test_retrieve_by_cefr_only_returns_matching_level(self):
        results = question_retriever.retrieve_questions(cefr_level="A1", limit=20)
        self.assertGreater(len(results), 0)
        for r in results:
            self.assertEqual(r["cefr_level"], "A1")

    # ---- spec test 2: retrieve by skill -------------------------------

    def test_retrieve_by_skill_only_returns_matching_skill(self):
        results = question_retriever.retrieve_questions(
            skill="vocabulary", limit=20,
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["skill"], "vocabulary")

    # ---- spec test 3: retrieve by grammar topic -----------------------

    def test_retrieve_by_grammar_topic_filters_to_topic(self):
        results = question_retriever.retrieve_questions(
            grammar_topic="present-simple", limit=20,
        )
        self.assertGreater(len(results), 0)
        for r in results:
            self.assertEqual(r["grammar_topic"], "Present simple")

    def test_retrieve_by_grammar_topic_is_case_insensitive_on_name(self):
        results = question_retriever.retrieve_questions(
            grammar_topic="present simple", limit=20,
        )
        self.assertGreater(len(results), 0)

    # ---- spec test 4: no result fallback ------------------------------

    def test_no_result_returns_empty_list(self):
        results = question_retriever.retrieve_questions(
            cefr_level="C2", skill="pronunciation", limit=5,
        )
        self.assertEqual(results, [])

    # ---- spec test 5: only active + approved ---------------------------

    def test_unreviewed_items_are_excluded(self):
        _ex("Sneaky unreviewed item.", is_reviewed=False,
            skill_obj=self.skill_grammar, topic_obj=self.topic_present_simple)
        results = question_retriever.retrieve_questions(cefr_level="A1", limit=50)
        for r in results:
            self.assertNotIn("Sneaky", r["question"])

    def test_inactive_items_are_excluded(self):
        _ex("Hidden inactive item.", is_active=False,
            skill_obj=self.skill_grammar, topic_obj=self.topic_present_simple)
        results = question_retriever.retrieve_questions(cefr_level="A1", limit=50)
        for r in results:
            self.assertNotIn("Hidden", r["question"])

    # ---- ranking semantics --------------------------------------------

    def test_keyword_query_ranks_matching_questions_first(self):
        results = question_retriever.retrieve_questions(
            cefr_level="A1", query="apple", limit=5,
        )
        self.assertGreater(len(results), 0)
        # The 'I have ___ apple.' item must be first.
        self.assertIn("apple", results[0]["question"].lower())

    def test_difficulty_proximity_breaks_ties(self):
        # Add an item with difficulty very close to the target.
        _ex("Closely-targeted item.", difficulty=0.5,
            skill_obj=self.skill_grammar, topic_obj=self.topic_present_simple)
        results = question_retriever.retrieve_questions(
            cefr_level="A1", difficulty=0.5, limit=5,
        )
        self.assertEqual(results[0]["question"], "Closely-targeted item.")


class GeneratedQuestionInclusionTests(TestCase):
    """Approved staging items should be retrievable; unapproved ones
    must not be."""

    def setUp(self):
        GeneratedQuestion.objects.create(
            code="qf-test-approved", question_type="multiple_choice",
            cefr_level="A2", skill="grammar",
            question_text="Approved staging Q.",
            correct_answer="ok", options=["a", "b", "c", "ok"],
            explanation="explained",
            quality_score=85, is_active=True, is_reviewed=True,
            approved_for_training=True, content_hash="h-app",
        )
        GeneratedQuestion.objects.create(
            code="qf-test-unapproved", question_type="multiple_choice",
            cefr_level="A2", skill="grammar",
            question_text="Unapproved staging Q.",
            correct_answer="ok", options=["a", "b", "c", "ok"],
            explanation="explained",
            quality_score=85, is_active=True, is_reviewed=True,
            approved_for_training=False, content_hash="h-unapp",
        )

    def test_approved_generated_question_is_included(self):
        results = question_retriever.retrieve_questions(
            cefr_level="A2", skill="grammar", limit=10,
        )
        questions = [r["question"] for r in results]
        self.assertIn("Approved staging Q.", questions)

    def test_unapproved_generated_question_is_excluded(self):
        results = question_retriever.retrieve_questions(
            cefr_level="A2", skill="grammar", limit=10,
        )
        questions = [r["question"] for r in results]
        self.assertNotIn("Unapproved staging Q.", questions)


class ExampleRetrieverTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        AITrainingExample.objects.create(
            task_type="error_analysis", cefr_level="B1", skill="grammar",
            input={"question": "He has gone yesterday.",
                   "student_answer": "gone", "correct_answer": "went"},
            output={"error_type": "tense", "correction": "went",
                    "severity": 3, "explanation": "Use past simple."},
            content_hash="h-er-1", is_approved=True, quality_score=90,
        )
        AITrainingExample.objects.create(
            task_type="error_analysis", cefr_level="B2", skill="grammar",
            input={"student_answer": "the the the", "correct_answer": "the"},
            output={"error_type": "duplication", "explanation": "..."},
            content_hash="h-er-2", is_approved=True, quality_score=70,
        )
        AITrainingExample.objects.create(
            task_type="error_analysis", cefr_level="B1", skill="grammar",
            input={"x": "y"}, output={"explanation": "..."},
            content_hash="h-er-3", is_approved=False, quality_score=85,
        )

    def test_retrieve_examples_filters_by_task_and_level(self):
        results = example_retriever.retrieve_examples(
            task_type="error_analysis", cefr_level="B1", limit=5,
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["cefr_level"], "B1")

    def test_unapproved_examples_excluded_by_default(self):
        results = example_retriever.retrieve_examples(
            task_type="error_analysis", limit=10,
        )
        self.assertEqual(len(results), 2)  # the third row is unapproved

    def test_query_keyword_re_ranks(self):
        results = example_retriever.retrieve_examples(
            task_type="error_analysis", query="duplication", limit=2,
        )
        self.assertEqual(len(results), 2)
        # The duplication-related row should rank first.
        self.assertEqual(results[0]["output"]["error_type"], "duplication")


class RetrievalServiceDispatchTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        skill = Skill.objects.create(name="Grammar A1",
                                     category="grammar", cefr_level="A1")
        _ex("She walks home, A1 grammar.", cefr="A1", skill_obj=skill)
        AITrainingExample.objects.create(
            task_type="answer_explanation", cefr_level="A1", skill="grammar",
            input={"question": "She ___ home.", "student_answer": "go",
                   "correct_answer": "goes"},
            output={"explanation": "Third-person singular adds -s."},
            content_hash="h-ax-1", is_approved=True, quality_score=88,
        )

    def test_exercise_generation_dispatch_uses_questions(self):
        bundle = retrieval_service.retrieve_examples(
            "exercise_generation", cefr_level="A1", skill="grammar", limit=3,
        )
        self.assertEqual(bundle["source"], "questions")
        self.assertGreater(bundle["count"], 0)
        self.assertEqual(bundle["context"]["task"], "exercise_generation")

    def test_answer_explanation_dispatch_uses_training_examples(self):
        bundle = retrieval_service.retrieve_examples(
            "answer_explanation", cefr_level="A1", skill="grammar", limit=3,
        )
        self.assertEqual(bundle["source"], "training_examples")
        self.assertEqual(bundle["count"], 1)

    def test_no_result_returns_empty_bundle(self):
        bundle = retrieval_service.retrieve_examples(
            "tutor_reply", cefr_level="C2", limit=3,
        )
        self.assertEqual(bundle["count"], 0)
        self.assertEqual(bundle["source"], "none")
        self.assertEqual(bundle["items"], [])
        self.assertEqual(bundle["context"], {})

    def test_fallback_from_question_bank_for_answer_explanation(self):
        # Wipe the curated training example so the service must fall back.
        AITrainingExample.objects.all().delete()
        bundle = retrieval_service.retrieve_examples(
            "answer_explanation", cefr_level="A1", skill="grammar", limit=3,
        )
        self.assertEqual(bundle["source"], "fallback")
        self.assertGreater(bundle["count"], 0)
        # Items have been re-shaped to (input, output) pairs.
        self.assertIn("input", bundle["items"][0])
        self.assertIn("output", bundle["items"][0])


class ContextBuilderTests(TestCase):
    def test_exercise_generation_context_trims_long_text(self):
        long_question = "x " * 500
        bundle = context_builder.build_exercise_generation_context(
            [{
                "cefr_level": "A1", "skill": "grammar",
                "question": long_question,
                "options": ["a", "b", "c", "d"],
                "correct_answer": "a",
                "explanation": "exp",
            }],
        )
        first = bundle["reference_questions"][0]
        self.assertLess(len(first["question"]), 300)
        self.assertTrue(first["question"].endswith("…"))

    def test_build_for_task_dispatch_chooses_right_builder(self):
        out = context_builder.build_for_task(
            "tutor_reply",
            items=[{
                "input": {"student_question": "hello"},
                "output": {"tutor_reply": "Hi! Welcome."},
            }],
            weaknesses=[{"skill": "grammar", "topic": "present_simple"}],
        )
        self.assertEqual(out["task"], "tutor_reply")
        self.assertEqual(len(out["reference_dialogues"]), 1)
        self.assertEqual(len(out["student_weaknesses"]), 1)
