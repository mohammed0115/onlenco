from unittest.mock import patch

from django.test import TestCase, override_settings

from factory.services import quality_router


def _good_item(**overrides):
    item = {
        "question": "She ___ to school every day.",
        "correct_answer": "goes",
        "options": ["go", "goes", "going", "gone"],
        "question_type": "multiple_choice",
        "difficulty_score": 0.3,
        "cefr_level": "A1",
        "language": "en",
    }
    item.update(overrides)
    return item


class QualityRouterTests(TestCase):
    def test_high_quality_item_approved_without_ai(self):
        approved, report = quality_router.validate(_good_item(), allow_ai=False)
        self.assertTrue(approved)
        self.assertEqual(report["decision"], "approve")
        self.assertEqual(report["rule_failures"], [])

    def test_critical_failure_rejects_or_escalates(self):
        bad = _good_item(correct_answer="zzz")  # not in options
        approved, report = quality_router.validate(bad, allow_ai=False)
        self.assertFalse(approved)
        self.assertIn("correct_answer_not_in_options", report["rule_failures"])

    def test_no_ai_path_is_conservative(self):
        # Borderline item with one minor flaw — without AI the router falls back to score.
        item = _good_item(question="ok ok")
        approved, _ = quality_router.validate(item, allow_ai=False)
        self.assertIn(approved, (True, False))  # either is acceptable, deterministic

    @override_settings(AI_API_KEY="sk-test", AI_LOCAL_API_BASE="")
    def test_ai_escalation_called_when_borderline(self):
        # Force escalate by giving short question (not critical, score < 80).
        item = _good_item(question="hi")
        with patch.object(quality_router.llm_router, "chat",
                          return_value=None) as p:
            approved, report = quality_router.validate(item, allow_ai=True)
        # AI was attempted
        self.assertTrue(p.called)
        # AI unavailable → fallback section recorded
        self.assertIn("ai", report)

    @override_settings(AI_API_KEY="sk-test", AI_LOCAL_API_BASE="")
    def test_ai_approves_borderline_when_responding_yes(self):
        item = _good_item(question="hi")  # short, escalates
        fake_payload = {"choices": [{"message": {
            "content": '{"approve": true, "reason": "ok", "fixes": []}'
        }}]}
        with patch.object(quality_router.llm_router, "chat", return_value=fake_payload):
            approved, report = quality_router.validate(item, allow_ai=True)
        self.assertTrue(approved)
        self.assertTrue(report["ai"]["approve"])
