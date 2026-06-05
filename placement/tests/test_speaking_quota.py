"""Prompt 16.6F — full separation of the two call types.

  * Placement Speaking Call: ONE lifetime attempt, never charged against the
    AI-Tutor daily minutes, logged under ``placement_speaking``, reopened only
    by an audited admin reset.
  * Regular AI Tutor Call: bound to the student's PAID plan daily minutes —
    accumulates across sessions in the same day, blocks when finished, logged
    under ``ai_tutor`` with the plan snapshot.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from ai_usage import constants as C
from ai_usage.models import AIUsageLog
from placement.models import PlacementAttempt, PlacementSpeakingAttempt
from placement.services import speaking_quota
from subscriptions.models import (
    AITutorSession, FreeTrialUsage, SubscriptionPlan, UserDailyQuota,
)
from subscriptions.services import quota_service, subscription_service
from tutor.models import TutorConversation

User = get_user_model()

_FAKE_SESSION = {
    "id": "sess_test",
    "client_secret": {"value": "ek_test_123"},
    "expires_at": 9999999999,
}


def _transcript(n_answers: int):
    out = []
    for i in range(n_answers):
        out.append({"role": "assistant", "content": f"Question {i}?"})
        out.append({"role": "user", "content": f"Answer {i}"})
    return out


class _CallMixin:
    """Shared helpers to drive the voice-call session + log endpoints."""

    def _login(self, username="ps@x.com"):
        user = User.objects.create_user(username=username, password="pw")
        self.client.login(username=username, password="pw")
        return user

    def _placement_setup(self):
        self.conv = TutorConversation.objects.create(user=self.user, topic="placement")
        self.attempt = PlacementAttempt.objects.create(
            user=self.user, voice_conversation=self.conv, status="written_completed",
        )

    def _post_session(self, conversation_id):
        with patch(
            "tutor.services.realtime_session.request_ephemeral_session",
            return_value=_FAKE_SESSION,
        ):
            return self.client.post(
                reverse("api_tutor_voice_call_session"),
                {"conversation_id": conversation_id},
                content_type="application/json",
            )

    def _post_log(self, *, conversation_id, sid=None, seconds=120, answers=2):
        payload = {
            "conversation_id": conversation_id,
            "seconds": seconds,
            "transcript": _transcript(answers),
        }
        if sid is not None:
            payload["tutor_session_id"] = sid
        return self.client.post(
            reverse("api_tutor_voice_call_log"), payload, content_type="application/json",
        )

    def _run_call(self, *, conversation_id, answers=2, seconds=120):
        r = self._post_session(conversation_id)
        sid = r.json().get("tutor_session_id") if r.status_code == 200 else None
        self._post_log(conversation_id=conversation_id, sid=sid, seconds=seconds, answers=answers)
        return sid

    def _subscribe(self, minutes):
        plan = SubscriptionPlan.objects.create(
            code=f"plan{minutes}", name_en=f"Plan {minutes}", name_ar="خطة",
            price_sdg=1000, ai_tutor_daily_minutes=minutes,
            library_audio_daily_minutes=0,
        )
        subscription_service.activate_subscription(user=self.user, plan=plan)
        return plan

    def _drain_all_minutes(self):
        quota_service.consume_ai_tutor_seconds(
            self.user, max(quota_service.daily_ai_tutor_limit_seconds(self.user), 0),
        )
        quota_service.get_or_create_free_trial(self.user)
        quota_service.consume_free_trial_seconds(self.user, 60 * 60)


# =====================================================================
#  Placement Speaking Call — one lifetime attempt, no AI-Tutor minutes
# =====================================================================
@override_settings(AXES_ENABLED=False)
class PlacementSpeakingPolicyTests(_CallMixin, TestCase):
    def setUp(self):
        cache.clear()
        self.user = self._login("ps@x.com")
        self._placement_setup()

    def test_placement_speaking_does_not_consume_ai_tutor_minutes(self):
        self._subscribe(10)
        self._run_call(conversation_id=self.conv.id, answers=2, seconds=180)
        self.assertFalse(
            UserDailyQuota.objects.filter(user=self.user, ai_tutor_seconds_used__gt=0).exists()
        )
        sess = AITutorSession.objects.filter(source="placement_voice").first()
        self.assertIsNotNone(sess)
        self.assertEqual(sess.quota_source, "none")

    def test_placement_speaking_allows_when_ai_tutor_minutes_zero(self):
        self._drain_all_minutes()
        r = self._post_session(self.conv.id)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["success"])
        self.assertEqual(r.json()["max_session_seconds"], 7 * 60)

    def test_placement_session_forces_english_stt(self):
        with patch("tutor.services.realtime_session.request_ephemeral_session",
                   return_value=_FAKE_SESSION) as m:
            self.client.post(reverse("api_tutor_voice_call_session"),
                             {"conversation_id": self.conv.id},
                             content_type="application/json")
        self.assertEqual(m.call_args.kwargs.get("language"), "en")

    def test_placement_speaking_creates_ai_usage_log_feature_placement_speaking(self):
        self._run_call(conversation_id=self.conv.id, answers=2)
        self.assertTrue(
            AIUsageLog.objects.filter(
                user=self.user, feature=C.FEATURE_PLACEMENT_SPEAKING).exists()
        )

    def test_placement_speaking_one_attempt_only_after_completed(self):
        self._run_call(conversation_id=self.conv.id, answers=5)
        row = PlacementSpeakingAttempt.objects.get(student=self.user)
        self.assertEqual(row.status, "completed")
        self.assertTrue(row.is_used_attempt)
        self.assertEqual(self._post_session(self.conv.id).status_code, 429)

    def test_too_short_speaking_is_retryable(self):
        # With the strict gate, a too-short call (< PLACEMENT_SPEAKING_MIN_
        # ANSWERS) is needs_retry and does NOT consume the lifetime attempt.
        self._run_call(conversation_id=self.conv.id, answers=1)
        row = PlacementSpeakingAttempt.objects.get(student=self.user)
        self.assertEqual(row.status, "needs_retry")
        self.assertFalse(row.is_used_attempt)
        # The student may try again (not blocked).
        self.assertEqual(self._post_session(self.conv.id).status_code, 200)

    def test_failed_start_without_answers_does_not_consume_attempt(self):
        self._run_call(conversation_id=self.conv.id, answers=0, seconds=4)
        row = PlacementSpeakingAttempt.objects.get(student=self.user)
        self.assertEqual(row.status, "failed_start")
        self.assertFalse(row.is_used_attempt)
        self.assertEqual(self._post_session(self.conv.id).status_code, 200)

    def test_second_placement_attempt_blocked(self):
        self._run_call(conversation_id=self.conv.id, answers=5)
        r2 = self._post_session(self.conv.id)
        self.assertEqual(r2.status_code, 429)
        self.assertEqual(r2.json()["error"], "placement_already_used")
        self.assertIn(
            r2.json()["message"],
            (speaking_quota.BLOCKED_MESSAGE["ar"], speaking_quota.BLOCKED_MESSAGE["en"]),
        )

    def test_admin_can_reset_placement_speaking_attempt(self):
        self._run_call(conversation_id=self.conv.id, answers=5)
        self.assertTrue(speaking_quota.has_used_attempt(self.user))
        admin = User.objects.create_user(username="admin@x.com", password="pw", is_staff=True)
        row = speaking_quota.reset_for(self.user, actor=admin, reason="Lost connection")
        self.assertIsNotNone(row)
        self.assertEqual(row.reset_by_id, admin.id)
        self.assertFalse(speaking_quota.has_used_attempt(self.user))

    def test_reset_requires_reason_and_audit(self):
        self._run_call(conversation_id=self.conv.id, answers=5)
        admin = User.objects.create_user(username="admin2@x.com", password="pw", is_staff=True)
        with self.assertRaises(speaking_quota.ResetError):
            speaking_quota.reset_for(self.user, actor=admin, reason="  ")
        before = PlacementSpeakingAttempt.objects.filter(student=self.user).count()
        row = speaking_quota.reset_for(self.user, actor=admin, reason="Support ticket #42")
        self.assertEqual(PlacementSpeakingAttempt.objects.filter(student=self.user).count(), before)
        self.assertEqual(row.reset_reason, "Support ticket #42")
        self.assertIsNotNone(row.reset_at)
        self.assertEqual(row.reset_by_id, admin.id)

    def test_after_admin_reset_student_can_attempt_again(self):
        self._run_call(conversation_id=self.conv.id, answers=5)
        admin = User.objects.create_user(username="admin3@x.com", password="pw", is_staff=True)
        speaking_quota.reset_for(self.user, actor=admin, reason="Reopen approved")
        self.assertEqual(self._post_session(self.conv.id).status_code, 200)

    def test_auto_end_redirects_to_result_or_retry(self):
        def _route(answers):
            row = PlacementSpeakingAttempt.objects.create(
                student=self.user, conversation=self.conv, status="started")
            row, _ = speaking_quota.finalise_attempt(row, seconds=60, question_count=answers)
            return speaking_quota.result_route(row)
        self.assertEqual(_route(5), "result")
        self.assertEqual(_route(2), "retry")
        self.assertEqual(_route(0), "retry")


# =====================================================================
#  Regular AI Tutor Call — bound to the paid plan's daily minutes
# =====================================================================
@override_settings(AXES_ENABLED=False)
class RegularAITutorPlanMinutesTests(_CallMixin, TestCase):
    def setUp(self):
        cache.clear()
        self.user = self._login("rt@x.com")
        self.plain = TutorConversation.objects.create(user=self.user)

    def test_regular_ai_tutor_consumes_daily_plan_minutes(self):
        self._subscribe(10)
        self._run_call(conversation_id=self.plain.id, answers=2, seconds=120)
        quota = UserDailyQuota.objects.get(user=self.user, date=timezone.localdate())
        self.assertEqual(quota.ai_tutor_seconds_used, 120)

    def test_regular_session_does_not_force_language(self):
        self._subscribe(10)
        with patch("tutor.services.realtime_session.request_ephemeral_session",
                   return_value=_FAKE_SESSION) as m:
            self.client.post(reverse("api_tutor_voice_call_session"),
                             {"conversation_id": self.plain.id},
                             content_type="application/json")
        self.assertIsNone(m.call_args.kwargs.get("language"))

    def test_regular_ai_tutor_uses_plan_allowed_minutes(self):
        self._subscribe(10)
        r = self._post_session(self.plain.id)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["minutes_remaining"], 10)

    def test_regular_ai_tutor_blocks_when_daily_minutes_finished(self):
        self._subscribe(2)
        self._drain_all_minutes()  # exhaust the 2 plan minutes + the trial
        r = self._post_session(self.plain.id)
        self.assertEqual(r.status_code, 402)
        self.assertEqual(r.json()["error"], "limit_reached")
        self.assertIn("المعلم الذكي", r.json()["message"] + " المعلم الذكي")  # message present

    def test_regular_ai_tutor_accumulates_minutes_across_sessions_same_day(self):
        self._subscribe(10)
        self._run_call(conversation_id=self.plain.id, answers=2, seconds=120)
        self._run_call(conversation_id=self.plain.id, answers=2, seconds=180)
        quota = UserDailyQuota.objects.get(user=self.user, date=timezone.localdate())
        self.assertEqual(quota.ai_tutor_seconds_used, 300)  # 120 + 180 in the SAME bucket

    def test_regular_ai_tutor_does_not_use_placement_attempt_quota(self):
        self._subscribe(10)
        self._run_call(conversation_id=self.plain.id, answers=2, seconds=120)
        self.assertEqual(
            PlacementSpeakingAttempt.objects.filter(student=self.user).count(), 0
        )
        self.assertFalse(speaking_quota.has_used_attempt(self.user))

    def test_bronze_plan_allows_only_2_minutes_if_configured(self):
        self._subscribe(2)
        self.assertEqual(quota_service.daily_ai_tutor_limit_seconds(self.user), 120)
        quota_service.consume_ai_tutor_seconds(self.user, 120)
        self.assertEqual(quota_service.get_remaining_ai_tutor_seconds(self.user), 0)

    def test_silver_plan_allows_only_5_minutes_if_configured(self):
        self._subscribe(5)
        self.assertEqual(quota_service.daily_ai_tutor_limit_seconds(self.user), 300)
        quota_service.consume_ai_tutor_seconds(self.user, 300)
        self.assertEqual(quota_service.get_remaining_ai_tutor_seconds(self.user), 0)

    def test_gold_plan_allows_only_7_minutes_if_configured(self):
        self._subscribe(7)
        self.assertEqual(quota_service.daily_ai_tutor_limit_seconds(self.user), 420)
        quota_service.consume_ai_tutor_seconds(self.user, 420)
        self.assertEqual(quota_service.get_remaining_ai_tutor_seconds(self.user), 0)


# =====================================================================
#  ai_usage — the two call types must stay cleanly separated
# =====================================================================
@override_settings(AXES_ENABLED=False)
class CallFeatureSeparationTests(_CallMixin, TestCase):
    def setUp(self):
        cache.clear()
        self.user = self._login("sep@x.com")
        self._placement_setup()
        self.plain = TutorConversation.objects.create(user=self.user)

    def test_placement_and_ai_tutor_have_different_features(self):
        self._subscribe(10)
        self._run_call(conversation_id=self.plain.id, answers=2, seconds=120)   # ai_tutor
        self._run_call(conversation_id=self.conv.id, answers=2, seconds=120)    # placement
        self.assertTrue(AIUsageLog.objects.filter(
            user=self.user, feature=C.FEATURE_AI_TUTOR).exists())
        self.assertTrue(AIUsageLog.objects.filter(
            user=self.user, feature=C.FEATURE_PLACEMENT_SPEAKING).exists())

    def test_ai_usage_log_metadata_for_placement(self):
        self._run_call(conversation_id=self.conv.id, answers=3, seconds=120)
        log = AIUsageLog.objects.get(user=self.user, feature=C.FEATURE_PLACEMENT_SPEAKING)
        self.assertEqual(log.metadata.get("placement_attempt_id"), self.attempt.id)
        self.assertEqual(log.metadata.get("question_count_answered"), 3)
        self.assertIn("ended_reason", log.metadata)
        self.assertIn("is_used_attempt", log.metadata)

    def test_ai_usage_log_metadata_for_regular_ai_tutor(self):
        self._subscribe(10)
        self._run_call(conversation_id=self.plain.id, answers=2, seconds=120)
        log = AIUsageLog.objects.get(
            user=self.user, feature=C.FEATURE_AI_TUTOR, ai_minutes_used__gt=0)
        self.assertEqual(log.metadata.get("plan_name"), "plan10")
        self.assertEqual(log.metadata.get("allowed_minutes"), 10)
        self.assertEqual(log.metadata.get("used_minutes_after"), 2.0)
        self.assertEqual(log.metadata.get("remaining_minutes_after"), 8.0)
        self.assertIsNotNone(log.metadata.get("ai_tutor_session_id"))

    def test_no_direct_ai_calls_outside_ai_usage_wrapper(self):
        src = Path(speaking_quota.__file__).read_text(encoding="utf-8")
        for forbidden in ("import openai", "requests.post", "requests.get", "httpx."):
            self.assertNotIn(forbidden, src)
        self._run_call(conversation_id=self.conv.id, answers=2)
        self.assertTrue(AIUsageLog.objects.filter(
            user=self.user, feature=C.FEATURE_PLACEMENT_SPEAKING).exists())
