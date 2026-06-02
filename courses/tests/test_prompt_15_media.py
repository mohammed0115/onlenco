"""Prompt 15 — Media Generation Pilot tests (provider always mocked)."""
from __future__ import annotations

import base64
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from platform_admin import permissions as control_perms

from accounts.models import APPROVAL_APPROVED, APPROVAL_PENDING_ADMIN
from ai_usage import constants as AC
from ai_usage.models import AIUsageLog
from ai_usage.services import ai_client
from ai_usage.tests.helpers import FakeResponse
from courses.models import Lesson, LessonAudioScript, LessonImagePrompt
from courses.services import media_generation_service as svc

User = get_user_model()
SLUG = "onlenco-beginner"
BATCH = [2, 3, 4, 5, 6]


def _new(order):
    return Lesson.objects.filter(course__slug=SLUG, order=order).exclude(status="archived").first()


def _img_resp():
    return FakeResponse(json_data={"data": [{"b64_json": base64.b64encode(b"PNGDATA").decode()}]})


def _aud_resp():
    return FakeResponse(content=b"MP3DATA")


def _provider_side_effect(url, *a, **k):
    if "/images/generations" in url:
        return _img_resp()
    if "/audio/speech" in url:
        return _aud_resp()
    return FakeResponse(json_data={})


@override_settings(AI_API_KEY="sk-test", AI_USAGE_TRACKING_ENABLED=True,
                   ONLENCO_MEDIA_GENERATION_ENABLED=True)
class Prompt15MediaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_platform_roles", verbosity=0)
        call_command("seed_learning_skills", verbosity=0)
        call_command("seed_super_lesson_01", verbosity=0)
        call_command("seed_beginner_48_topics", "--confirm", verbosity=0)
        cls.admin = User.objects.create_superuser("m15@x.com", "m15@x.com", "pw12345!")
        call_command("approve_teacher_batch", "--course", SLUG, "--topics", "2-6",
                     "--confirm", "--actor", cls.admin.username, verbosity=0)
        call_command("publish_teacher_batch", "--course", SLUG, "--topics", "2-6",
                     "--confirm", "--actor", cls.admin.username, verbosity=0)

    def _student(self, u="ms@x.com", status=APPROVAL_APPROVED):
        user = User.objects.create_user(username=u, email=u, password="pw12345!")
        p = user.profile
        p.role = "student"; p.email_verified = True; p.approval_status = status
        p.save()
        return user

    def _teacher(self):
        u = User.objects.create_user("mt15@x.com", "mt15@x.com", "pw12345!")
        g, _ = Group.objects.get_or_create(name=control_perms.GROUP_TEACHER)
        u.groups.add(g)
        return u

    def _gen_image(self, order=2, ptype="cover"):
        ip = _new(order).image_prompts.filter(prompt_type=ptype).first()
        with mock.patch.object(ai_client.requests, "post", side_effect=_provider_side_effect):
            outcome, _ = svc.generate_lesson_image(ip, actor=self.admin)
        ip.refresh_from_db()
        return ip, outcome

    # ---------- lifecycle ----------
    def test_generated_media_created_as_needs_review(self):
        ip, outcome = self._gen_image()
        self.assertEqual(outcome, "generated")
        self.assertEqual(ip.generation_status, "needs_review")
        self.assertTrue(bool(ip.generated_image))
        self.assertIsNotNone(ip.ai_usage_log)

    def test_media_approve_changes_status(self):
        ip, _ = self._gen_image()
        svc.mark_media_approved(ip, self.admin, "ok")
        ip.refresh_from_db()
        self.assertEqual(ip.generation_status, "approved")
        self.assertEqual(ip.reviewed_by_id, self.admin.id)

    def test_media_reject_changes_status(self):
        ip, _ = self._gen_image()
        svc.mark_media_rejected(ip, self.admin, "bad")
        ip.refresh_from_db()
        self.assertEqual(ip.generation_status, "rejected")

    def test_student_visibility_requires_media_approval(self):
        ip, _ = self._gen_image()
        self.assertFalse(ip.is_student_visible)        # needs_review
        svc.mark_media_approved(ip, self.admin)
        ip.refresh_from_db()
        self.assertTrue(ip.is_student_visible)         # approved

    # ---------- command ----------
    def test_generate_lesson_media_batch_dry_run(self):
        call_command("generate_lesson_media_batch", "--course", SLUG, "--topics", "2-6",
                     "--media", "all", "--dry-run", stdout=StringIO())
        self.assertEqual(LessonImagePrompt.objects.filter(
            lesson__in=[_new(o) for o in BATCH]).exclude(generated_image="").count(), 0)

    def test_generate_lesson_media_batch_no_media_generated_without_confirm(self):
        # Same as dry-run: omitting --confirm must not write.
        call_command("generate_lesson_media_batch", "--course", SLUG, "--topics", "2-2",
                     "--media", "images", stdout=StringIO())
        self.assertEqual(AIUsageLog.objects.count(), 0)

    def test_generate_lesson_media_batch_confirm_images(self):
        with mock.patch.object(ai_client.requests, "post", side_effect=_provider_side_effect):
            call_command("generate_lesson_media_batch", "--course", SLUG, "--topics", "2-2",
                         "--media", "images", "--confirm", "--allow-dev-generation",
                         "--budget-usd", "2.00", stdout=StringIO())
        gen = LessonImagePrompt.objects.filter(lesson=_new(2), generation_status="needs_review")
        self.assertEqual(gen.count(), 4)

    def test_generate_lesson_media_batch_confirm_audio(self):
        with mock.patch.object(ai_client.requests, "post", side_effect=_provider_side_effect):
            call_command("generate_lesson_media_batch", "--course", SLUG, "--topics", "2-2",
                         "--media", "audio", "--confirm", "--allow-dev-generation",
                         "--budget-usd", "3.00", stdout=StringIO())
        self.assertEqual(LessonAudioScript.objects.filter(
            lesson=_new(2), generation_status="needs_review").count(), 6)

    def test_generate_lesson_media_batch_refuses_topics_07_48(self):
        with self.assertRaises(CommandError):
            call_command("generate_lesson_media_batch", "--course", SLUG, "--topics", "7-9",
                         "--media", "all", "--dry-run", stdout=StringIO())

    def test_generate_lesson_media_batch_refuses_pending_review(self):
        # A pending lesson in range is not eligible → no media for it.
        from courses.services import lesson_review_workflow as wf
        wf.unpublish(actor=self.admin, lesson=_new(2), note="x")  # → approved (still eligible)
        # Force it pending to prove ineligibility.
        L = _new(2); L.status = "pending_review"; L.save(update_fields=["status"])
        with mock.patch.object(ai_client.requests, "post", side_effect=_provider_side_effect):
            call_command("generate_lesson_media_batch", "--course", SLUG, "--topics", "2-2",
                         "--media", "images", "--confirm", "--allow-dev-generation", stdout=StringIO())
        self.assertEqual(LessonImagePrompt.objects.filter(
            lesson=_new(2)).exclude(generated_image="").count(), 0)

    def test_generate_lesson_media_batch_budget_limit(self):
        # Tiny budget < one audio est cost → nothing generated.
        with mock.patch.object(ai_client.requests, "post", side_effect=_provider_side_effect):
            call_command("generate_lesson_media_batch", "--course", SLUG, "--topics", "2-2",
                         "--media", "audio", "--confirm", "--allow-dev-generation",
                         "--budget-usd", "0.0001", stdout=StringIO())
        self.assertEqual(LessonAudioScript.objects.filter(
            lesson=_new(2), generation_status="needs_review").count(), 0)

    def test_generate_lesson_media_batch_skips_existing_without_replace(self):
        self._gen_image(2, "cover")  # pre-generate one
        out = StringIO()
        with mock.patch.object(ai_client.requests, "post", side_effect=_provider_side_effect):
            call_command("generate_lesson_media_batch", "--course", SLUG, "--topics", "2-2",
                         "--media", "images", "--confirm", "--allow-dev-generation", stdout=out)
        self.assertIn("skipped", out.getvalue())

    def test_generate_lesson_media_batch_requires_enabled_flag(self):
        with override_settings(ONLENCO_MEDIA_GENERATION_ENABLED=False):
            with self.assertRaises(CommandError):
                call_command("generate_lesson_media_batch", "--course", SLUG, "--topics", "2-2",
                             "--media", "images", "--confirm", stdout=StringIO())

    # ---------- AI usage ----------
    def test_image_generation_logs_ai_usage(self):
        self._gen_image()
        log = AIUsageLog.objects.filter(feature=AC.FEATURE_MEDIA_GENERATION).latest("id")
        self.assertEqual(log.status, AC.STATUS_SUCCESS)

    def test_audio_generation_logs_ai_usage(self):
        sc = _new(2).audio_scripts.first()
        with mock.patch.object(ai_client.requests, "post", side_effect=_provider_side_effect):
            svc.generate_lesson_audio(sc, actor=self.admin)
        log = AIUsageLog.objects.filter(feature=AC.FEATURE_TTS).latest("id")
        self.assertEqual(log.status, AC.STATUS_SUCCESS)
        self.assertGreater(log.audio_output_seconds, 0)

    def test_failed_media_generation_logs_usage(self):
        ip = _new(3).image_prompts.first()
        with mock.patch.object(ai_client.requests, "post", side_effect=RuntimeError("boom")):
            outcome, _ = svc.generate_lesson_image(ip, actor=self.admin)
        self.assertEqual(outcome, "failed")
        ip.refresh_from_db()
        self.assertEqual(ip.generation_status, "failed")
        self.assertTrue(AIUsageLog.objects.filter(
            feature=AC.FEATURE_MEDIA_GENERATION, status=AC.STATUS_FAILED).exists())

    def test_unsafe_image_prompt_skips_provider(self):
        ip = _new(4).image_prompts.first()
        ip.prompt = "A cartoon Duolingo owl mascot"
        ip.save(update_fields=["prompt"])
        with mock.patch.object(ai_client.requests, "post") as post:
            outcome, detail = svc.generate_lesson_image(ip, actor=self.admin)
        post.assert_not_called()
        self.assertEqual(outcome, "failed")
        self.assertIn("unsafe_word", detail)

    def test_media_generation_uses_wrapper_not_direct_provider(self):
        # The service must reach the provider only via ai_client.requests.
        ip = _new(5).image_prompts.filter(prompt_type="cover").first()
        with mock.patch.object(ai_client.requests, "post", side_effect=_provider_side_effect) as post:
            svc.generate_lesson_image(ip, actor=self.admin)
        self.assertTrue(post.called)

    # ---------- student rendering ----------
    @override_settings(ONLENCO_STUDENT_APPROVAL_REQUIRED=True)
    def test_student_sees_placeholder_before_approval(self):
        ip, _ = self._gen_image(2, "cover")   # needs_review
        self.client.force_login(self._student())
        L = _new(2)
        resp = self.client.get(reverse("courses:lesson_step",
                                       kwargs={"course_pk": L.course_id, "lesson_pk": L.id,
                                               "step_kind": "vocabulary"}))
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn(ip.generated_image.url, resp.content.decode())

    @override_settings(ONLENCO_STUDENT_APPROVAL_REQUIRED=True)
    def test_student_sees_approved_image_after_approval(self):
        ip, _ = self._gen_image(2, "cover")
        svc.mark_media_approved(ip, self.admin)
        ip.refresh_from_db()
        self.client.force_login(self._student("ms2@x.com"))
        L = _new(2)
        resp = self.client.get(reverse("courses:lesson_step",
                                       kwargs={"course_pk": L.course_id, "lesson_pk": L.id,
                                               "step_kind": "vocabulary"}))
        self.assertEqual(resp.status_code, 200)
        self.assertIn(ip.generated_image.url, resp.content.decode())

    @override_settings(ONLENCO_STUDENT_APPROVAL_REQUIRED=True)
    def test_student_never_sees_raw_prompt_or_script(self):
        ip, _ = self._gen_image(2, "cover")
        self.client.force_login(self._student("ms3@x.com"))
        L = _new(2)
        resp = self.client.get(reverse("courses:lesson_step",
                                       kwargs={"course_pk": L.course_id, "lesson_pk": L.id,
                                               "step_kind": "vocabulary"}))
        self.assertNotIn(ip.prompt, resp.content.decode())

    # ---------- review dashboard ----------
    def test_teacher_can_review_generated_media(self):
        self._gen_image()
        self.client.force_login(self._teacher())
        resp = self.client.get(reverse("platform_admin:media_review") + "?status=needs_review")
        self.assertEqual(resp.status_code, 200)

    def test_student_cannot_access_media_review_dashboard(self):
        self.client.force_login(self._student("msd@x.com"))
        resp = self.client.get(reverse("platform_admin:media_review"))
        self.assertIn(resp.status_code, (302, 403))

    def test_approve_media_from_dashboard(self):
        ip, _ = self._gen_image()
        self.client.force_login(self._teacher())
        self.client.post(reverse("platform_admin:media_action", args=["image", ip.id, "approve"]),
                         {"note": "ok"})
        ip.refresh_from_db()
        self.assertEqual(ip.generation_status, "approved")

    def test_reject_media_from_dashboard(self):
        ip, _ = self._gen_image()
        self.client.force_login(self._teacher())
        self.client.post(reverse("platform_admin:media_action", args=["image", ip.id, "reject"]),
                         {"note": "no"})
        ip.refresh_from_db()
        self.assertEqual(ip.generation_status, "rejected")

    # ---------- cleanup ----------
    def test_cleanup_generated_media_dry_run(self):
        ip, _ = self._gen_image()
        call_command("cleanup_generated_media_batch", "--course", SLUG, "--topics", "2-6",
                     "--dry-run", "--only-status", "needs_review", stdout=StringIO())
        ip.refresh_from_db()
        self.assertEqual(ip.generation_status, "needs_review")  # unchanged

    def test_cleanup_marks_needs_review_media_hidden(self):
        ip, _ = self._gen_image()
        call_command("cleanup_generated_media_batch", "--course", SLUG, "--topics", "2-6",
                     "--confirm", "--only-status", "needs_review", stdout=StringIO())
        ip.refresh_from_db()
        self.assertEqual(ip.generation_status, "rejected")
        self.assertFalse(ip.is_student_visible)

    def test_cleanup_does_not_delete_approved_media_by_default(self):
        ip, _ = self._gen_image()
        svc.mark_media_approved(ip, self.admin)
        call_command("cleanup_generated_media_batch", "--course", SLUG, "--topics", "2-6",
                     "--confirm", "--only-status", "approved", stdout=StringIO())
        ip.refresh_from_db()
        self.assertEqual(ip.generation_status, "approved")  # protected

    def test_cleanup_preserves_ai_usage_logs(self):
        self._gen_image()
        before = AIUsageLog.objects.count()
        call_command("cleanup_generated_media_batch", "--course", SLUG, "--topics", "2-6",
                     "--confirm", "--only-status", "needs_review", stdout=StringIO())
        self.assertEqual(AIUsageLog.objects.count(), before)

    # ---------- regression ----------
    def test_topics_02_06_remain_published(self):
        self._gen_image()
        for o in BATCH:
            self.assertEqual(_new(o).status, "published")

    def test_topics_07_48_remain_pending_review(self):
        self._gen_image()
        self.assertEqual(Lesson.objects.filter(course__slug=SLUG, status="pending_review").count(), 42)

    def test_no_media_generated_for_topics_07_48(self):
        with mock.patch.object(ai_client.requests, "post", side_effect=_provider_side_effect):
            call_command("generate_lesson_media_batch", "--course", SLUG, "--topics", "2-6",
                         "--media", "all", "--confirm", "--allow-dev-generation", stdout=StringIO())
        self.assertEqual(LessonImagePrompt.objects.filter(
            lesson__course__slug=SLUG, lesson__order__gte=7).exclude(generated_image="").count(), 0)

    @override_settings(ONLENCO_STUDENT_APPROVAL_REQUIRED=True)
    def test_student_approval_gate_still_blocks_pending_students(self):
        self.client.force_login(self._student("mp@x.com", status=APPROVAL_PENDING_ADMIN))
        resp = self.client.get(reverse("dashboard"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/account/pending-approval", resp["Location"])
