"""Prompt 18.2G — student-facing QA: approved Beginner media renders in lesson
pages; pending/failed media never reaches the student; no technical tokens."""
from __future__ import annotations

import re

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from courses.models import Course, Lesson

User = get_user_model()


class BeginnerMediaStudentQaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_onlenco_beginner_48_units", "--quiet")
        cls.course = Course.objects.get(slug="onlenco-beginner")
        # QA renders any lesson regardless of the daily drip unlock.
        cls.course.drip_enabled = False
        cls.course.save(update_fields=["drip_enabled"])

    def setUp(self):
        self.user = User.objects.create_user(username="qa@x.com", password="pw")
        p = self.user.profile
        p.subscription_status = "active"
        p.subscription_expires_at = timezone.now() + timezone.timedelta(days=30)
        p.save()
        self.client.login(username="qa@x.com", password="pw")

    # --- helpers -----------------------------------------------------------
    def _lesson(self, book_unit):
        return Lesson.objects.get(course=self.course, book_unit_number=book_unit)

    def _approve_image(self, lesson, ptype):
        p = lesson.image_prompts.filter(prompt_type=ptype).first()
        p.generated_image.save(f"{ptype}{lesson.order}.png", ContentFile(b"img"), save=False)
        p.is_generated = True
        p.generation_status = "approved"
        p.save()
        return p

    def _approve_audio(self, lesson, stype):
        s = lesson.audio_scripts.filter(script_type=stype).first()
        s.generated_audio.save(f"{stype}{lesson.order}.mp3", ContentFile(b"aud"), save=False)
        s.is_generated = True
        s.generation_status = "approved"
        s.save()
        return s

    def _step_url(self, lesson, kind):
        return reverse("courses:lesson_step",
                       args=[self.course.pk, lesson.pk, kind])

    # --- tests -------------------------------------------------------------
    def test_sample_lesson_pages_return_200(self):
        for bu in (1, 6, 12, 24, 36, 48):
            lesson = self._lesson(bu)
            url = reverse("courses:lesson_detail", args=[self.course.pk, lesson.pk])
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200, f"book_unit {bu} -> {r.status_code}")

    def test_approved_cover_and_audio_render_in_step(self):
        lesson = self._lesson(1)
        cover = self._approve_image(lesson, "cover")
        html = self.client.get(self._step_url(lesson, "intro")).content.decode()
        self.assertIn(cover.generated_image.url, html)   # approved cover visible
        # The combined recording plays on the dialogue step (it has no per-item
        # listen-repeat content). Listen-repeat steps (intro/examples/vocabulary)
        # deliberately use natural per-item clips, NOT the combined MP3.
        audio = self._approve_audio(lesson, "dialogue")
        dlg = self.client.get(self._step_url(lesson, "dialogue")).content.decode()
        self.assertIn(audio.generated_audio.url, dlg)    # approved combined audio present

    def test_approved_illustration_renders_in_vocabulary_step(self):
        lesson = self._lesson(6)
        voc = self._approve_image(lesson, "vocabulary")
        html = self.client.get(self._step_url(lesson, "vocabulary")).content.decode()
        self.assertIn(voc.generated_image.url, html)

    def test_pending_media_not_shown_to_student(self):
        lesson = self._lesson(12)
        # A pending vocabulary prompt (no file, not approved) must NOT render an
        # <img> URL or leak its raw prompt — only a clean placeholder.
        p = lesson.image_prompts.filter(prompt_type="vocabulary").first()
        p.generation_status = "needs_review"
        p.save()
        html = self.client.get(self._step_url(lesson, "vocabulary")).content.decode()
        self.assertNotIn("/lessons/image_prompts/", html)   # no real image URL
        if p.prompt:
            self.assertNotIn(p.prompt, html)                # raw prompt never shown

    def test_lesson_detail_hides_unapproved_cover(self):
        # A generated-but-unapproved cover must NOT appear on the lesson hero
        # (Prompt 18.2G bug fix): it stays the clean placeholder.
        lesson = self._lesson(24)
        p = lesson.image_prompts.filter(prompt_type="cover").first()
        p.generated_image.save("c24.png", ContentFile(b"img"), save=False)
        p.is_generated = True
        p.generation_status = "needs_review"   # NOT approved
        p.save()
        url = reverse("courses:lesson_detail", args=[self.course.pk, lesson.pk])
        html = self.client.get(url).content.decode()
        self.assertNotIn(p.generated_image.url, html)
        self.assertIn("onlenco-hero__cover-fallback", html)

    def test_lesson_step_has_no_technical_tokens_or_fast_playback(self):
        lesson = self._lesson(1)
        self._approve_image(lesson, "cover")
        self._approve_audio(lesson, "intro")
        html = self.client.get(self._step_url(lesson, "intro")).content.decode()
        low = html.lower()
        for token in ("openai", "gpt-image", "gpt-4o", "whisper", "needs_review",
                      "generation_status", "pending_generation"):
            self.assertNotIn(token, low)
        # Playback must never exceed natural speed for beginners.
        for rate in re.findall(r"playbackrate\s*=\s*([0-9]*\.?[0-9]+)", low):
            self.assertLessEqual(float(rate), 1.0)
