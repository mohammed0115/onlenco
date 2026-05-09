"""End-to-end tests for the bulk pipeline (`bulk_generation_service` +
`generate_questions` command).

These tests deliberately use small targets and a small set of seeded
blueprints so the suite stays fast — the spec says no test should
attempt to generate hundreds of thousands of records."""
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings

from question_factory import constants as C
from question_factory.models import (
    GeneratedQuestion, GenerationBatch, QuestionBlueprint,
)
from question_factory.services import bulk_generation_service as bulk
from question_factory.services.bulk_generation_service import (
    AIBudget, compute_quotas, run_generation,
)


# --------------------------------------------------------------------------
# Helpers — light blueprint fixtures so tests don't depend on the seed
# --------------------------------------------------------------------------

def _seed_blueprint(*, code: str, level: str, skill: str,
                    qtype: str = "multiple_choice",
                    pattern: str = "{subject} ___ to school every day.",
                    answer_expr: str = "verb.0 + 's'",
                    explanation_pattern: str = "",
                    variables: dict | None = None,
                    metadata: dict | None = None) -> QuestionBlueprint:
    return QuestionBlueprint.objects.create(
        code=code,
        title=code,
        cefr_level=level,
        skill=skill,
        question_type=qtype,
        template_pattern=pattern,
        expected_answer_pattern=answer_expr,
        # Default explanation_pattern is empty so callers don't have to
        # know about the renderer's strict-binding rule.
        explanation_pattern=explanation_pattern,
        variables_schema=variables or {
            "subject": ["she", "he", "the cat"],
            "verb":    [["walk", "walked"], ["play", "played"], ["cook", "cooked"]],
        },
        metadata=metadata or {"distractor_config": {"strategy": "morph"}},
    )


# --------------------------------------------------------------------------
# Quota math
# --------------------------------------------------------------------------

class QuotaComputationTests(TestCase):
    def test_full_distribution_sums_to_target(self):
        q = compute_quotas(100_000)
        # 49 cells (7 levels × 7 skills) — sum should be very close to 100k.
        self.assertAlmostEqual(sum(q.values()), 100_000, delta=10)
        self.assertEqual(set(k[0] for k in q), {"A0", "A1", "A2", "B1", "B2", "C1", "C2"})

    def test_level_filter_collapses_to_one_level(self):
        q = compute_quotas(1000, cefr_level="B1")
        self.assertTrue(all(k[0] == "B1" for k in q))
        self.assertAlmostEqual(sum(q.values()), 1000, delta=5)

    def test_skill_filter_collapses_to_one_skill(self):
        q = compute_quotas(1000, skill=C.SKILL_GRAMMAR)
        self.assertTrue(all(k[1] == C.SKILL_GRAMMAR for k in q))
        self.assertAlmostEqual(sum(q.values()), 1000, delta=5)

    def test_both_filters_single_cell(self):
        q = compute_quotas(500, cefr_level="A1", skill=C.SKILL_VOCABULARY)
        self.assertEqual(q, {("A1", C.SKILL_VOCABULARY): 500})

    def test_zero_cells_pruned(self):
        q = compute_quotas(10)  # very small target → some skill cells round to 0
        for v in q.values():
            self.assertGreater(v, 0)


# --------------------------------------------------------------------------
# AI budget
# --------------------------------------------------------------------------

class AIBudgetTests(TestCase):
    def test_zero_cap_means_no_quota(self):
        b = AIBudget(0)
        self.assertFalse(b.has_quota)

    def test_positive_cap_allows_then_exhausts(self):
        b = AIBudget(2)
        self.assertTrue(b.has_quota)
        b.spend(1)
        self.assertTrue(b.has_quota)
        b.spend(1)
        self.assertFalse(b.has_quota)

    def test_negative_cap_unlimited(self):
        b = AIBudget(-1)
        self.assertTrue(b.has_quota)
        b.spend(1000)
        self.assertTrue(b.has_quota)


# --------------------------------------------------------------------------
# Run-level behaviour
# --------------------------------------------------------------------------

@override_settings(AI_API_KEY="", AI_LOCAL_API_BASE="")
class RunGenerationTests(TestCase):
    def setUp(self):
        # One blueprint per (level, skill) combo we want to exercise.
        _seed_blueprint(code="bp-A1-grammar",
                        level="A1", skill=C.SKILL_GRAMMAR)
        _seed_blueprint(code="bp-A1-vocab",
                        level="A1", skill=C.SKILL_VOCABULARY,
                        pattern="What does '{w.0}' mean?",
                        answer_expr="w.1",
                        variables={"w": [["happy","feeling joy"],
                                          ["sad","feeling unhappy"],
                                          ["fast","quick"]]},
                        metadata={"distractor_config": {
                            "strategy": "from_pool",
                            "pool": ["unhappy", "tired", "lazy"],
                        }})

    # ------ dry-run -----------------------------------------------------

    def test_dry_run_writes_no_questions(self):
        before = GeneratedQuestion.objects.count()
        batch = run_generation(
            target_count=20, cefr_level="A1",
            batch_size=10, strategy=C.GEN_TEMPLATE, dry_run=True,
        )
        self.assertEqual(GeneratedQuestion.objects.count(), before)
        # The batch row IS persisted so operators can see what would happen.
        self.assertEqual(batch.status, C.BATCH_COMPLETED)
        self.assertGreater(batch.generated_count, 0)
        self.assertGreater(batch.accepted_count, 0)

    def test_dry_run_disables_ai(self):
        # Even when --max-ai-calls is non-zero, dry-run forces AI off.
        with patch("question_factory.services.bulk_generation_service"
                   ".ai_generator.generate_for_blueprint") as p:
            run_generation(
                target_count=10, cefr_level="A1", batch_size=10,
                strategy=C.GEN_AI, dry_run=True, max_ai_calls=999,
            )
        p.assert_not_called()

    # ------ small batch -------------------------------------------------

    def test_small_batch_persists(self):
        batch = run_generation(
            target_count=10, cefr_level="A1",
            batch_size=10, strategy=C.GEN_TEMPLATE,
        )
        self.assertEqual(batch.status, C.BATCH_COMPLETED)
        self.assertGreater(GeneratedQuestion.objects.filter(cefr_level="A1").count(), 0)

    # ------ duplicates --------------------------------------------------

    def test_idempotent_no_duplicate_codes(self):
        run_generation(
            target_count=10, cefr_level="A1", skill=C.SKILL_GRAMMAR,
            batch_size=10, strategy=C.GEN_TEMPLATE,
        )
        n1 = GeneratedQuestion.objects.count()
        run_generation(  # second run, same parameters
            target_count=10, cefr_level="A1", skill=C.SKILL_GRAMMAR,
            batch_size=10, strategy=C.GEN_TEMPLATE,
        )
        n2 = GeneratedQuestion.objects.count()
        self.assertEqual(n1, n2)
        codes = list(GeneratedQuestion.objects.values_list("code", flat=True))
        self.assertEqual(len(codes), len(set(codes)))

    # ------ resume ------------------------------------------------------

    def test_resume_reuses_existing_batch(self):
        b1 = run_generation(
            target_count=5, cefr_level="A1", skill=C.SKILL_GRAMMAR,
            batch_size=5, strategy=C.GEN_TEMPLATE,
        )
        # Fake a "still running" prior run by flipping status back.
        b1.status = C.BATCH_RUNNING
        b1.save(update_fields=["status"])
        b2 = run_generation(
            target_count=10, cefr_level="A1", skill=C.SKILL_GRAMMAR,
            batch_size=5, strategy=C.GEN_TEMPLATE, resume=True,
        )
        # Resume must reuse the same row, not create a fresh one.
        self.assertEqual(b1.batch_id, b2.batch_id)
        self.assertEqual(b2.target_count, 10)
        # And it must have made forward progress beyond the first run's count.
        self.assertGreater(
            GeneratedQuestion.objects.filter(cefr_level="A1").count(),
            b1.accepted_count,
        )

    # ------ quality threshold + invalid items --------------------------

    def test_quality_threshold_rejects_low_score(self):
        # Wire up a blueprint whose rendered answer is missing → triggers
        # `missing_correct_answer` (critical, score 70 - 30 = 40).
        _seed_blueprint(
            code="bp-bad", level="A0", skill=C.SKILL_GRAMMAR,
            pattern="{x} ___",
            answer_expr="''",  # empty string answer
            variables={"x": ["a", "b", "c"]},
        )
        batch = run_generation(
            target_count=5, cefr_level="A0", skill=C.SKILL_GRAMMAR,
            batch_size=5, strategy=C.GEN_TEMPLATE,
            quality_threshold=60,
        )
        # All candidates are rejected (none accepted).
        self.assertEqual(batch.accepted_count, 0)
        self.assertGreater(batch.rejected_count, 0)
        self.assertEqual(
            GeneratedQuestion.objects.filter(cefr_level="A0").count(),
            0,
        )

    # ------ AI failure fallback ----------------------------------------

    def test_ai_strategy_falls_back_to_template(self):
        # Patch the AI generator to return zero items — the dispatcher
        # should fall back to the template path and still write rows.
        with patch("question_factory.services.bulk_generation_service"
                   ".ai_generator.generate_for_blueprint",
                   return_value={"candidates": 0, "accepted": 0,
                                 "rejected": 0, "duplicates": 0,
                                 "served_by": None}):
            batch = run_generation(
                target_count=5, cefr_level="A1", skill=C.SKILL_GRAMMAR,
                batch_size=5, strategy=C.GEN_AI, max_ai_calls=10,
            )
        self.assertGreater(batch.accepted_count, 0)
        self.assertEqual(batch.status, C.BATCH_COMPLETED)

    def test_ai_strategy_handles_exception_gracefully(self):
        with patch("question_factory.services.bulk_generation_service"
                   ".ai_generator.generate_for_blueprint",
                   side_effect=RuntimeError("boom")):
            batch = run_generation(
                target_count=5, cefr_level="A1", skill=C.SKILL_GRAMMAR,
                batch_size=5, strategy=C.GEN_AI, max_ai_calls=10,
            )
        self.assertEqual(batch.status, C.BATCH_COMPLETED)
        self.assertGreater(batch.accepted_count, 0)

    # ------ AI cost cap ------------------------------------------------

    def test_max_ai_calls_caps_invocations(self):
        # Cap at 1 call. The first chunk uses AI; subsequent chunks must
        # degrade to template (no AI calls beyond the cap).
        ai_calls = 0

        def ai_stub(blueprint, **kwargs):
            nonlocal ai_calls
            ai_calls += 1
            return {"candidates": kwargs.get("count", 1),
                    "accepted": 0, "rejected": 0, "duplicates": 0,
                    "served_by": "test"}

        with patch("question_factory.services.bulk_generation_service"
                   ".ai_generator.generate_for_blueprint",
                   side_effect=ai_stub):
            run_generation(
                target_count=20, cefr_level="A1", skill=C.SKILL_GRAMMAR,
                batch_size=5, strategy=C.GEN_AI, max_ai_calls=1,
            )
        self.assertLessEqual(ai_calls, 1)

    # ------ review-required flag ---------------------------------------

    def test_review_required_marks_borderline_items(self):
        # First, generate with a low threshold so some borderline items
        # land in the staging table.
        run_generation(
            target_count=10, cefr_level="A1", skill=C.SKILL_GRAMMAR,
            batch_size=10, strategy=C.GEN_TEMPLATE, quality_threshold=40,
        )
        # Manually push a couple of items into the borderline range so
        # the post-processor has something to flip.
        for q in GeneratedQuestion.objects.all()[:2]:
            q.quality_score = 65
            q.is_active = True
            q.is_reviewed = False
            q.save(update_fields=["quality_score", "is_active", "is_reviewed"])
        # Re-run with review_required → should flip those into review.
        run_generation(
            target_count=10, cefr_level="A1", skill=C.SKILL_GRAMMAR,
            batch_size=10, strategy=C.GEN_TEMPLATE, quality_threshold=80,
            review_required=True,
        )
        self.assertGreaterEqual(
            GeneratedQuestion.objects.filter(
                metadata__review_required=True,
            ).count(),
            2,
        )


# --------------------------------------------------------------------------
# Management-command surface
# --------------------------------------------------------------------------

@override_settings(AI_API_KEY="", AI_LOCAL_API_BASE="")
class GenerateQuestionsCommandTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        _seed_blueprint(code="bp-cmd-grammar",
                        level="A1", skill=C.SKILL_GRAMMAR)

    def test_command_dry_run_writes_no_rows(self):
        out = StringIO()
        before = GeneratedQuestion.objects.count()
        call_command(
            "generate_questions",
            "--target-count", "20", "--batch-size", "10",
            "--cefr-level", "A1", "--skill", C.SKILL_GRAMMAR,
            "--strategy", C.GEN_TEMPLATE, "--dry-run",
            stdout=out,
        )
        self.assertEqual(GeneratedQuestion.objects.count(), before)
        self.assertIn("status=completed", out.getvalue())

    def test_command_template_run_persists(self):
        before = GeneratedQuestion.objects.count()
        call_command(
            "generate_questions",
            "--target-count", "5", "--batch-size", "5",
            "--cefr-level", "A1", "--skill", C.SKILL_GRAMMAR,
            "--strategy", C.GEN_TEMPLATE,
            stdout=StringIO(),
        )
        self.assertGreater(GeneratedQuestion.objects.count(), before)
        self.assertTrue(
            GenerationBatch.objects.filter(status=C.BATCH_COMPLETED).exists()
        )
