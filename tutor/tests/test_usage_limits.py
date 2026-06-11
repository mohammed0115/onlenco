"""Prompt 17.2 — unified AI-Tutor usage facade.

Service-level coverage of the daily-limit business rules and the placement /
regular separation, all through ``tutor.services.usage_limits``.
"""
from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from subscriptions.models import AITutorSession, SubscriptionPlan, UserSubscription
from tutor.services import usage_limits as ul


class UsageLimitsFacadeTests(TestCase):
    def setUp(self):
        self.User = get_user_model()

    def _subscribed(self, email, minutes):
        user = self.User.objects.create_user(username=email, email=email, password="pw")
        now = timezone.now()
        plan = SubscriptionPlan.objects.create(
            code=f"plan-{email}", name_en="Plan", name_ar="خطة", price_sdg=0,
            ai_tutor_daily_minutes=minutes, library_audio_daily_minutes=0,
        )
        UserSubscription.objects.create(
            user=user, plan=plan, status="active",
            start_date=now - timedelta(days=1), end_date=now + timedelta(days=29),
        )
        return user

    # --- read API -----------------------------------------------------------
    def test_allowed_seconds_match_plan(self):
        u = self._subscribed("allowed@x.com", 2)
        self.assertEqual(ul.get_daily_allowed_seconds(u), 120)

    # --- rule 5/6: hard daily block ----------------------------------------
    def test_plan_2min_blocks_after_120s(self):
        u = self._subscribed("two@x.com", 2)
        ul.deduct_voice_message_usage(u, 120)
        self.assertEqual(ul.get_remaining_seconds(u), 0)
        self.assertFalse(ul.can_start_ai_tutor_usage(u, ul.MODE_REGULAR_AI_TUTOR_CALL))
        with self.assertRaises(ul.UsageLimitError):
            ul.assert_can_use_ai_tutor(u, ul.MODE_REGULAR_AI_TUTOR_CALL)

    def test_plan_5min_blocks_after_300s(self):
        u = self._subscribed("five@x.com", 5)
        ul.deduct_voice_message_usage(u, 300)
        self.assertEqual(ul.get_remaining_seconds(u), 0)
        with self.assertRaises(ul.UsageLimitError):
            ul.assert_can_use_ai_tutor(u, ul.MODE_REGULAR_AI_TUTOR_VOICE_MESSAGE)

    # --- rule 7: accumulate within a day -----------------------------------
    def test_multiple_sessions_accumulate(self):
        u = self._subscribed("accum@x.com", 5)
        ul.deduct_voice_message_usage(u, 60)
        ul.deduct_voice_message_usage(u, 90)
        self.assertEqual(ul.get_daily_used_seconds(u), 150)
        self.assertEqual(ul.get_remaining_seconds(u), 150)

    # --- rule 8: reset next day --------------------------------------------
    def test_usage_resets_next_day(self):
        u = self._subscribed("reset@x.com", 5)
        ul.deduct_voice_message_usage(u, 200)
        tomorrow = timezone.localdate() + timedelta(days=1)
        self.assertEqual(ul.get_daily_used_seconds(u, tomorrow), 0)
        self.assertEqual(ul.get_remaining_seconds(u, tomorrow), 300)

    # --- rule 1/5: placement never consumes --------------------------------
    def test_placement_call_does_not_consume(self):
        u = self._subscribed("place@x.com", 5)
        before = ul.get_remaining_seconds(u)
        usage = ul.start_ai_tutor_usage(u, ul.MODE_PLACEMENT_SPEAKING_CALL)
        self.assertFalse(usage.consumes_minutes)
        self.assertIsNotNone(usage.session_id)
        ul.finalize_ai_tutor_usage(usage, 90)
        self.assertEqual(ul.get_remaining_seconds(u), before)
        self.assertEqual(ul.get_daily_used_seconds(u), 0)

    def test_placement_opens_placement_voice_session_only(self):
        u = self._subscribed("placesrc@x.com", 5)
        usage = ul.start_ai_tutor_usage(u, ul.MODE_PLACEMENT_SPEAKING_CALL)
        sess = AITutorSession.objects.get(pk=usage.session_id)
        self.assertEqual(sess.source, "placement_voice")
        ul.finalize_ai_tutor_usage(usage, 80)
        sess.refresh_from_db()
        self.assertEqual(sess.quota_source, "none")
        self.assertEqual(ul.get_daily_used_seconds(u), 0)

    # --- rule 2/6: regular call consumes on finalize -----------------------
    def test_regular_call_consumes_on_finalize(self):
        u = self._subscribed("call@x.com", 5)
        usage = ul.start_ai_tutor_usage(u, ul.MODE_REGULAR_AI_TUTOR_CALL)
        self.assertIsNotNone(usage.session_id)
        self.assertTrue(usage.consumes_minutes)
        ul.finalize_ai_tutor_usage(usage, 60)
        self.assertEqual(ul.get_daily_used_seconds(u), 60)
        self.assertEqual(ul.get_remaining_seconds(u), 240)

    # --- rule 3: voice message consumes ------------------------------------
    def test_voice_message_consumes(self):
        u = self._subscribed("vmsg@x.com", 5)
        usage = ul.start_ai_tutor_usage(u, ul.MODE_REGULAR_AI_TUTOR_VOICE_MESSAGE)
        self.assertIsNone(usage.session_id)
        ul.finalize_ai_tutor_usage(usage, 30)
        self.assertEqual(ul.get_daily_used_seconds(u), 30)

    def test_voice_message_idempotent_key_prevents_double_charge(self):
        u = self._subscribed("idem@x.com", 5)
        ul.deduct_voice_message_usage(u, 40, idempotency_key="abc")
        ul.deduct_voice_message_usage(u, 40, idempotency_key="abc")
        self.assertEqual(ul.get_daily_used_seconds(u), 40)

    def test_voice_message_no_duration_uses_fallback(self):
        u = self._subscribed("fallback@x.com", 5)
        ul.deduct_voice_message_usage(u, 0)
        self.assertEqual(ul.get_daily_used_seconds(u), ul._voice_message_fallback_seconds())

    # --- rule 4/9: text message does not consume by default ----------------
    def test_text_message_does_not_consume_by_default(self):
        u = self._subscribed("text@x.com", 5)
        self.assertFalse(ul.is_minute_bearing_mode(ul.MODE_REGULAR_AI_TUTOR_MESSAGE))
        usage = ul.start_ai_tutor_usage(u, ul.MODE_REGULAR_AI_TUTOR_MESSAGE)
        ul.finalize_ai_tutor_usage(usage, 30)
        self.assertEqual(ul.get_daily_used_seconds(u), 0)

    @override_settings(TUTOR_TEXT_MESSAGE_CONSUMES_MINUTES=True)
    def test_text_message_consumes_when_configured(self):
        u = self._subscribed("textcfg@x.com", 5)
        self.assertTrue(ul.is_minute_bearing_mode(ul.MODE_REGULAR_AI_TUTOR_MESSAGE))
        usage = ul.start_ai_tutor_usage(u, ul.MODE_REGULAR_AI_TUTOR_MESSAGE)
        ul.finalize_ai_tutor_usage(usage, 20)
        self.assertEqual(ul.get_daily_used_seconds(u), 20)

    # --- rule 8 (blocked): reserve raises when exhausted -------------------
    def test_start_call_raises_when_exhausted(self):
        u = self._subscribed("exhaust@x.com", 2)
        ul.deduct_voice_message_usage(u, 120)
        with self.assertRaises(ul.UsageLimitError):
            ul.start_ai_tutor_usage(u, ul.MODE_REGULAR_AI_TUTOR_CALL)

    def test_voice_message_blocked_when_limit_reached(self):
        u = self._subscribed("vblock@x.com", 2)
        ul.deduct_voice_message_usage(u, 120)
        with self.assertRaises(ul.UsageLimitError) as ctx:
            ul.assert_can_use_ai_tutor(u, ul.MODE_REGULAR_AI_TUTOR_VOICE_MESSAGE)
        self.assertIn("اليومي", ctx.exception.message_ar)
