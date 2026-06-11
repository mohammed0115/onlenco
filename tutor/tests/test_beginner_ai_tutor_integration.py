"""Prompt 18.4B — AI Tutor + Beginner Course combined student smoke.

Proves the AI Tutor works *beside* the Beginner A0 course without breaking
course access, lesson progress, Daily Quiz, the Weekly gate, AI usage limits,
or the CEFR language policy. Smoke/QA only — no AI Tutor rebuild, no policy
change, no migration. The model is never called for real: the `chat` seam is
mocked, and usage is exercised through the existing facade.
"""
from __future__ import annotations

import json
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts import onboarding as onboarding_lib
from courses.models import Course, CourseLessonProgress, Lesson
from subscriptions.models import SubscriptionPlan, UserSubscription
from tutor.models import TutorConversation
from tutor.services import prompt_builder as pb
from tutor.services import usage_limits as ul

User = get_user_model()


def _subscribe(user, minutes):
    now = timezone.now()
    plan = SubscriptionPlan.objects.create(
        code=f"plan-{user.username}", name_en="P", name_ar="خطة", price_sdg=0,
        ai_tutor_daily_minutes=minutes, library_audio_daily_minutes=0,
    )
    UserSubscription.objects.create(
        user=user, plan=plan, status="active",
        start_date=now - timedelta(days=1), end_date=now + timedelta(days=29),
    )
    prof = user.profile
    prof.subscription_status = "active"
    prof.subscription_expires_at = now + timedelta(days=29)
    prof.save()


@override_settings(AXES_ENABLED=False)
class BeginnerAiTutorIntegrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_onlenco_beginner_48_units", "--quiet")
        cls.course = Course.objects.get(slug="onlenco-beginner")
        cls.course.drip_enabled = False
        cls.course.save(update_fields=["drip_enabled"])
        cls.first_unit = cls.course.units.order_by("order").first()
        cls.unit_lessons = list(
            Lesson.objects.filter(course=cls.course, unit=cls.first_unit).order_by("order")
        )

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username="combo@x.com", password="pw")
        onboarding_lib.complete_beginner_onboarding(self.user)   # A0, beginner_start
        _subscribe(self.user, 10)                                # 600s AI minutes
        self.lesson = Lesson.objects.get(course=self.course, book_unit_number=1)
        self._approve_media(self.lesson)
        self.client.login(username="combo@x.com", password="pw")
        self.chat_url = reverse("api_tutor_chat_send")

    # --- helpers -----------------------------------------------------------
    def _approve_media(self, lesson):
        p = lesson.image_prompts.filter(prompt_type="cover").first()
        p.generated_image.save("c.png", ContentFile(b"img"), save=False)
        p.is_generated = True
        p.generation_status = "approved"
        p.save()
        s = lesson.audio_scripts.filter(script_type="intro").first()
        s.generated_audio.save("a.mp3", ContentFile(b"aud"), save=False)
        s.is_generated = True
        s.generation_status = "approved"
        s.save()

    def _detail_url(self):
        return reverse("courses:course_detail", args=[self.course.pk])

    def _mark_complete(self, lesson):
        return self.client.post(
            reverse("courses:mark_lesson_complete", args=[self.course.pk, lesson.pk]))

    def _send_chat(self, text="Hello"):
        # `chat` is the only model seam — patched so no real API is hit.
        with patch("tutor.api.views.chat", return_value="Hello! مرحبا.") as mocked:
            r = self.client.post(
                self.chat_url,
                {"message": text, "conversation_id": self.conv().id},
                content_type="application/json")
        return r, mocked

    def conv(self):
        if not hasattr(self, "_conv"):
            self._conv = TutorConversation.objects.create(user=self.user)
        return self._conv

    def _daily_plan(self):
        from daily_learning.models import DailyLearningPlan
        return DailyLearningPlan.objects.get(user=self.user, date=timezone.localdate())

    # === A) combined journey ==============================================
    def test_course_then_tutor_then_course_roundtrip(self):
        self.assertEqual(self.client.get(self._detail_url()).status_code, 200)
        step = reverse("courses:lesson_step", args=[self.course.pk, self.lesson.pk, "intro"])
        html = self.client.get(step).content.decode()
        self.assertIn(self.lesson.image_prompts.filter(prompt_type="cover").first()
                      .generated_image.url, html)               # media still visible
        self.assertIn(self._mark_complete(self.lesson).status_code, (302, 303))
        r, mocked = self._send_chat()
        self.assertEqual(r.status_code, 200)
        mocked.assert_called_once()                              # mock used, no real API
        self.assertEqual(self.client.get(self._detail_url()).status_code, 200)

    def test_ai_tutor_does_not_break_progress(self):
        self._mark_complete(self.lesson)
        before = CourseLessonProgress.objects.get(user=self.user, lesson=self.lesson)
        before_video, before_count = before.video_completed, CourseLessonProgress.objects.count()
        self._send_chat()
        after = CourseLessonProgress.objects.get(user=self.user, lesson=self.lesson)
        self.assertEqual(after.video_completed, before_video)
        self.assertEqual(CourseLessonProgress.objects.count(), before_count)

    def test_daily_quiz_works_after_ai_tutor(self):
        self._send_chat()
        self.assertEqual(self.client.get("/daily/").status_code, 200)
        item = self._daily_plan().items.filter(item_type="quiz").first()
        r = self.client.post(
            f"/daily/items/{item.id}/complete/",
            data=json.dumps({"answer": item.correct_answer}),
            content_type="application/json")
        self.assertTrue(r.json()["is_correct"])

    def test_weekly_gate_after_three_lessons_with_tutor(self):
        self._send_chat()
        for le in self.unit_lessons[:3]:
            CourseLessonProgress.objects.create(
                user=self.user, lesson=le, completed_at=timezone.now())
        html = self.client.get(self._detail_url()).content.decode()
        self.assertIn("weekly-review-card", html)

    # === B) usage-limit smoke =============================================
    def test_text_chat_does_not_deduct_minutes(self):
        before = ul.get_remaining_seconds(self.user)
        r, _ = self._send_chat()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(ul.get_remaining_seconds(self.user), before)   # text is free

    def test_regular_voice_message_deducts(self):
        before = ul.get_remaining_seconds(self.user)
        u = ul.start_ai_tutor_usage(self.user, ul.MODE_REGULAR_AI_TUTOR_VOICE_MESSAGE)
        ul.finalize_ai_tutor_usage(u, 30)
        self.assertLess(ul.get_remaining_seconds(self.user), before)    # voice consumes

    def test_regular_call_deducts(self):
        before = ul.get_remaining_seconds(self.user)
        u = ul.start_ai_tutor_usage(self.user, ul.MODE_REGULAR_AI_TUTOR_CALL)
        ul.finalize_ai_tutor_usage(u, 45)
        self.assertLess(ul.get_remaining_seconds(self.user), before)

    def test_double_finalize_does_not_double_deduct(self):
        u = ul.start_ai_tutor_usage(self.user, ul.MODE_REGULAR_AI_TUTOR_CALL)
        ul.finalize_ai_tutor_usage(u, 60)
        once = ul.get_remaining_seconds(self.user)
        ul.finalize_ai_tutor_usage(u, 60)                               # idempotent
        self.assertEqual(ul.get_remaining_seconds(self.user), once)

    def test_exhausted_usage_returns_arabic_state(self):
        ul.deduct_usage_seconds(self.user, 10_000)                      # burn the day
        self.assertFalse(ul.can_start_regular_ai_tutor_session(self.user))
        with self.assertRaises(ul.UsageLimitError) as ctx:
            ul.assert_can_use_ai_tutor(self.user, ul.MODE_REGULAR_AI_TUTOR_CALL)
        self.assertIn("انتهى", ctx.exception.message_ar)                # safe Arabic
        self.assertEqual(ctx.exception.info["message"]["ar"], ctx.exception.message_ar)

    # === C) placement vs regular separation ===============================
    def test_placement_voice_does_not_deduct_regular_minutes(self):
        before = ul.get_remaining_seconds(self.user)
        u = ul.start_ai_tutor_usage(self.user, ul.MODE_PLACEMENT_SPEAKING_CALL)
        self.assertFalse(u.consumes_minutes)
        ul.finalize_ai_tutor_usage(u, 120)
        self.assertEqual(ul.get_remaining_seconds(self.user), before)   # placement is free
        self.assertFalse(ul.is_minute_bearing_mode(ul.MODE_PLACEMENT_SPEAKING_CALL))

    def test_daily_quiz_does_not_deduct_tutor_minutes(self):
        self.client.get("/daily/")
        before = ul.get_remaining_seconds(self.user)
        item = self._daily_plan().items.filter(item_type="quiz").first()
        self.client.post(
            f"/daily/items/{item.id}/complete/",
            data=json.dumps({"answer": item.correct_answer}),
            content_type="application/json")
        self.assertEqual(ul.get_remaining_seconds(self.user), before)

    # === D) CEFR language policy ==========================================
    def test_a0_language_policy_is_beginner_friendly(self):
        pol = pb.get_language_policy("A0")
        self.assertTrue(pol["arabic_support"])
        self.assertTrue(pol["keep_short"])
        self.assertEqual(pol["reply_language"], "ar_primary")

    def test_levels_do_not_bleed_into_a0(self):
        self.assertEqual(pb.get_language_policy("A2")["reply_language"], "en_with_ar_gloss")
        self.assertEqual(pb.get_language_policy("B1")["reply_language"], "en")
        self.assertFalse(pb.get_language_policy("B1")["arabic_support"])

    def test_a0_call_opening_is_simple(self):
        opening = pb.build_opening_instruction(self.user, ul.MODE_REGULAR_AI_TUTOR_CALL)
        self.assertIn("Begin", opening)
        self.assertIn("beginner", opening.lower())               # A0 beginner clause
        self.assertNotIn("openai", opening.lower())

    # === E) technical sanitization ========================================
    def test_sanitization_strips_technical_artifacts(self):
        raw = 'Use openai gpt-4o, see config.json {"k":1} and file___name now.'
        out = pb.sanitize_tutor_output_text(raw, level="A0", language="ar")
        for bad in ("openai", "gpt-4o", ".json", "{", "}", "___"):
            self.assertNotIn(bad, out)

    def test_all_technical_input_falls_back_to_arabic(self):
        out = pb.sanitize_tutor_output_text('{"x": 1} ```code``` file.py', level="A0", language="ar")
        self.assertEqual(out, "حاول مرة أخرى بجملة قصيرة.")        # _SAFE_FALLBACK_AR

    # === F) AI Tutor does not touch the daily plan score ==================
    def test_chat_does_not_create_or_alter_daily_plan(self):
        from daily_learning.models import DailyLearningPlan
        before = DailyLearningPlan.objects.filter(user=self.user).count()
        self._send_chat()
        self.assertEqual(DailyLearningPlan.objects.filter(user=self.user).count(), before)
