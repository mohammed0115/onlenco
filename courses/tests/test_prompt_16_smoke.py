"""Prompt 16 — live-media smoke-test selectors + visibility (provider mocked)."""
from __future__ import annotations

import base64
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import APPROVAL_APPROVED
from ai_usage.services import ai_client
from ai_usage.tests.helpers import FakeResponse
from courses.models import Lesson, LessonImagePrompt
from courses.services import media_generation_service as svc

User = get_user_model()
SLUG = "onlenco-beginner"


def _new(o):
    return Lesson.objects.filter(course__slug=SLUG, order=o).exclude(status="archived").first()


def _side(url, *a, **k):
    if "/images/generations" in url:
        return FakeResponse(json_data={"data": [{"b64_json": base64.b64encode(b"PNG").decode()}]})
    if "/audio/speech" in url:
        return FakeResponse(content=b"MP3")
    return FakeResponse(json_data={})


@override_settings(AI_API_KEY="sk-test", AI_USAGE_TRACKING_ENABLED=True,
                   ONLENCO_MEDIA_GENERATION_ENABLED=True)
class Prompt16SmokeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_platform_roles", verbosity=0)
        call_command("seed_learning_skills", verbosity=0)
        call_command("seed_super_lesson_01", verbosity=0)
        call_command("seed_beginner_48_topics", "--confirm", verbosity=0)
        cls.admin = User.objects.create_superuser("p16@x.com", "p16@x.com", "pw12345!")
        call_command("approve_teacher_batch", "--course", SLUG, "--topics", "2-6",
                     "--confirm", "--actor", cls.admin.username, verbosity=0)
        call_command("publish_teacher_batch", "--course", SLUG, "--topics", "2-6",
                     "--confirm", "--actor", cls.admin.username, verbosity=0)

    def _student(self, u="p16s@x.com"):
        user = User.objects.create_user(username=u, email=u, password="pw12345!")
        p = user.profile
        p.role = "student"; p.email_verified = True; p.approval_status = APPROVAL_APPROVED
        p.save()
        return user

    def _smoke_one_image(self):
        with mock.patch.object(ai_client.requests, "post", side_effect=_side):
            call_command("generate_lesson_media_batch", "--course", SLUG, "--topics", "2",
                         "--media", "images", "--purpose", "cover", "--limit", "1",
                         "--confirm", "--allow-dev-generation", "--budget-usd", "0.50",
                         stdout=StringIO())

    def test_single_item_media_smoke_generation_limit(self):
        self._smoke_one_image()
        gen = LessonImagePrompt.objects.filter(
            lesson=_new(2), generation_status="needs_review")
        self.assertEqual(gen.count(), 1)
        self.assertEqual(gen.first().prompt_type, "cover")
        # the other 3 image prompts were NOT generated
        self.assertEqual(LessonImagePrompt.objects.filter(
            lesson=_new(2)).exclude(generation_status="needs_review").exclude(
            generated_image="").count(), 0)

    @override_settings(ONLENCO_STUDENT_APPROVAL_REQUIRED=True)
    def test_approved_media_becomes_student_visible(self):
        self._smoke_one_image()
        ip = LessonImagePrompt.objects.get(lesson=_new(2), prompt_type="cover")
        self.assertFalse(ip.is_student_visible)
        svc.mark_media_approved(ip, self.admin, "QA 9/10 — clear and on-topic")
        ip.refresh_from_db()
        self.client.force_login(self._student())
        L = _new(2)
        resp = self.client.get(reverse("courses:lesson_step",
                                       kwargs={"course_pk": L.course_id, "lesson_pk": L.id,
                                               "step_kind": "vocabulary"}))
        self.assertEqual(resp.status_code, 200)
        self.assertIn(ip.generated_image.url, resp.content.decode())

    @override_settings(ONLENCO_STUDENT_APPROVAL_REQUIRED=True)
    def test_rejected_media_keeps_placeholder(self):
        self._smoke_one_image()
        ip = LessonImagePrompt.objects.get(lesson=_new(2), prompt_type="cover")
        svc.mark_media_rejected(ip, self.admin, "blurry")
        ip.refresh_from_db()
        self.client.force_login(self._student("p16s2@x.com"))
        L = _new(2)
        resp = self.client.get(reverse("courses:lesson_step",
                                       kwargs={"course_pk": L.course_id, "lesson_pk": L.id,
                                               "step_kind": "vocabulary"}))
        self.assertNotIn(ip.generated_image.url, resp.content.decode())

    def test_real_media_review_notes_saved(self):
        self._smoke_one_image()
        ip = LessonImagePrompt.objects.get(lesson=_new(2), prompt_type="cover")
        svc.mark_media_approved(ip, self.admin, "Smoke QA: approved 9/10")
        ip.refresh_from_db()
        self.assertEqual(ip.review_notes, "Smoke QA: approved 9/10")
        self.assertEqual(ip.reviewed_by_id, self.admin.id)
        self.assertIsNotNone(ip.reviewed_at)

    def test_budget_guard_still_works(self):
        with mock.patch.object(ai_client.requests, "post", side_effect=_side):
            call_command("generate_lesson_media_batch", "--course", SLUG, "--topics", "2",
                         "--media", "audio", "--purpose", "intro", "--limit", "1",
                         "--confirm", "--allow-dev-generation", "--budget-usd", "0.0001",
                         stdout=StringIO())
        from courses.models import LessonAudioScript
        self.assertEqual(LessonAudioScript.objects.filter(
            lesson=_new(2), generation_status="needs_review").count(), 0)

    def test_topics_07_48_untouched_after_smoke_test(self):
        self._smoke_one_image()
        self.assertEqual(LessonImagePrompt.objects.filter(
            lesson__course__slug=SLUG, lesson__order__gte=7)
            .exclude(generated_image="").count(), 0)
        self.assertEqual(Lesson.objects.filter(course__slug=SLUG, status="pending_review").count(), 42)
