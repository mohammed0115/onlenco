from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings

from placement.models import PlacementAttemptQuestion
from placement.services.dynamic_scoring import (
    build_dynamic_assessment_payload,
    score_placement_attempt,
)
from placement.services.placement_question_selector import create_placement_attempt


User = get_user_model()


@override_settings(AI_API_KEY="")
class DynamicScoringServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_placement_questions", stdout=StringIO())

    def setUp(self):
        self.user = User.objects.create_user(username="dynscore@x.com", password="pw")
        self.attempt = create_placement_attempt(self.user)
        for index, aq in enumerate(
            self.attempt.questions.filter(section="written").order_by("order"),
            start=1,
        ):
            aq.user_answer_text = (
                f"Written answer {index}. I study English every day and want to improve."
            )
            aq.save(update_fields=["user_answer_text"])
        for index, aq in enumerate(
            self.attempt.questions.filter(section="speaking").order_by("order"),
            start=1,
        ):
            aq.transcript = (
                f"Speaking answer {index}. I practice English because I need it for work."
            )
            aq.save(update_fields=["transcript"])

    def test_payload_contains_all_dynamic_questions_and_metadata(self):
        payload = build_dynamic_assessment_payload(self.attempt)

        self.assertEqual(payload["mode"], "dynamic")
        self.assertEqual(len(payload["items"]), 10)
        sample = payload["items"][0]
        for key in (
            "code",
            "section",
            "question_text",
            "skill",
            "topic",
            "difficulty_score",
            "expected_answer_type",
            "answer",
        ):
            self.assertIn(key, sample)

    def test_scoring_persists_per_question_scores(self):
        result = score_placement_attempt(self.attempt)

        self.assertIn(result["level"], ["A0", "A1", "A2", "B1", "B2", "C1", "C2"])
        self.assertIn("grammar_score", result)
        self.assertIn("vocabulary_score", result)
        self.assertIn("fluency_score", result)
        self.assertIn("overall_score", result)
        scored_rows = list(
            PlacementAttemptQuestion.objects.filter(
                attempt=self.attempt,
                score__isnull=False,
            )
        )
        self.assertEqual(len(scored_rows), 10)
        self.assertTrue(all(row.feedback for row in scored_rows))
        self.assertTrue(all(row.completed_at for row in scored_rows))
        self.assertTrue(all(row.skill_score is not None for row in scored_rows))
        self.assertTrue(all(row.grammar_score is not None for row in scored_rows))
        self.assertTrue(all(row.vocabulary_score is not None for row in scored_rows))
        self.assertTrue(
            all(row.fluency_score is not None for row in scored_rows if row.section == "speaking")
        )
        self.assertTrue(all(row.pronunciation_score is None for row in scored_rows))
        speaking_row = next(row for row in scored_rows if row.section == "speaking")
        self.assertFalse(speaking_row.error_analysis["pronunciation"]["available"])
        self.assertEqual(result["transcript"]["mode"], "dynamic")
        self.assertEqual(len(result["transcript"]["written"]), 5)
        self.assertEqual(len(result["transcript"]["speaking"]), 5)

    def test_final_scores_are_derived_from_all_question_scores(self):
        ordered_rows = list(
            self.attempt.questions.select_related("question").order_by("section", "order", "id")
        )
        written_scores = [10, 20, 30, 40, 50]
        speaking_scores = [60, 70, 80, 90, 100]

        def fake_assessor(payload):
            rows = []
            written_index = 0
            speaking_index = 0
            for item in payload["items"]:
                if item["section"] == "written":
                    score = written_scores[written_index]
                    written_index += 1
                    fluency = None
                else:
                    score = speaking_scores[speaking_index]
                    speaking_index += 1
                    fluency = score
                rows.append({
                    "attempt_question_id": item["attempt_question_id"],
                    "score": score,
                    "skill_score": score,
                    "grammar_score": score,
                    "vocabulary_score": score,
                    "fluency_score": fluency,
                    "feedback": f"Score {score}",
                    "error_analysis": {"source": "test_assessor"},
                })
            return {"feedback": "Question-based scoring complete.", "question_scores": rows}

        result = score_placement_attempt(self.attempt, assessor=fake_assessor)

        self.assertEqual(len(ordered_rows), 10)
        self.assertEqual(result["written_score"], 30)
        self.assertEqual(result["speaking_score"], 80)
        self.assertEqual(result["grammar_score"], 55)
        self.assertEqual(result["vocabulary_score"], 55)
        self.assertEqual(result["fluency_score"], 80)
        self.assertIsNone(result["pronunciation_score"])
        self.assertEqual(result["overall_score"], 55)
        self.assertEqual(result["level"], "B1")

        rows = list(
            PlacementAttemptQuestion.objects.filter(attempt=self.attempt).order_by("section", "order")
        )
        self.assertEqual([int(row.score) for row in rows if row.section == "written"], written_scores)
        self.assertEqual([int(row.score) for row in rows if row.section == "speaking"], speaking_scores)
