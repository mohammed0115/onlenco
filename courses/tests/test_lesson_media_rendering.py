"""Prompt 16.6A.4 — student lesson media rendering + internal-text scrubbing.

Reuses the super-lesson seed helpers (course `onlenco-beginner`, lesson 1).
"""
from io import StringIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from courses.models import CourseEnrollment, Lesson
from courses.tests.test_super_lesson_01 import (
    _get_lesson_quiz, _login, _make_student, _seed_all,
)

STEPS = ["intro", "vocabulary", "examples", "dialogue", "listening", "speaking", "finish"]


class LessonStepInternalTextTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        _seed_all()
        cls.course, cls.lesson, cls.quiz = _get_lesson_quiz()
        cls.student = _make_student("media-internal")
        CourseEnrollment.objects.get_or_create(user=cls.student, course=cls.course)

    def _body(self, kind):
        r = _login(self.student).get(
            reverse("courses:lesson_step", args=[self.course.pk, self.lesson.pk, kind]),
            HTTP_HOST="127.0.0.1",
        )
        self.assertEqual(r.status_code, 200, kind)
        return r.content.decode()

    def test_student_lesson_steps_do_not_show_phase_95_text(self):
        for kind in STEPS:
            body = self._body(kind)
            self.assertNotIn("Phase 9.5", body, f"leaked Phase 9.5 in {kind}")
            self.assertNotIn("Visual placeholder for steps", body, kind)
            self.assertNotIn("associated LessonImagePrompt", body, kind)

    def test_student_lesson_steps_do_not_show_template_comment_markers(self):
        for kind in STEPS:
            body = self._body(kind)
            self.assertNotIn("{#", body, kind)
            self.assertNotIn("#}", body, kind)
            self.assertNotIn("NEVER renders", body, kind)


class LessonStepAudioRenderingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        _seed_all()
        cls.course, cls.lesson, cls.quiz = _get_lesson_quiz()
        cls.student = _make_student("media-audio")
        CourseEnrollment.objects.get_or_create(user=cls.student, course=cls.course)

    def _intro_script(self):
        s = self.lesson.audio_scripts.filter(script_type="intro").first()
        self.assertIsNotNone(s, "seed should create an intro audio script")
        return s

    def _body(self, kind="intro"):
        return _login(self.student).get(
            reverse("courses:lesson_step", args=[self.course.pk, self.lesson.pk, kind]),
            HTTP_HOST="127.0.0.1",
        ).content.decode()

    def _attach_audio(self, script, status):
        script.generated_audio.save(
            "intro_test.mp3", SimpleUploadedFile("intro_test.mp3", b"ID3\x03audio"), save=False)
        script.generation_status = status
        script.save()

    def test_audio_placeholder_when_audio_not_generated(self):
        body = self._body("intro")
        self.assertNotIn('class="onlenco-mega-player"', body)      # no unapproved player leaks
        # intro is a listen-and-repeat step → tappable Listen button (per-item audio).
        self.assertTrue('data-lr-start' in body or 'onlenco-stage__pending' in body)

    def test_audio_player_renders_when_approved_audio_file_exists(self):
        s = self._intro_script()
        self._attach_audio(s, "approved")
        body = self._body("intro")
        self.assertIn('class="onlenco-mega-player"', body)
        self.assertIn(s.generated_audio.url, body)
        self.assertNotIn('class="onlenco-stage__pending"', body)

    def test_audio_placeholder_when_audio_needs_review(self):
        self._attach_audio(self._intro_script(), "needs_review")
        body = self._body("intro")
        self.assertNotIn('class="onlenco-mega-player"', body)   # no unapproved player leaks
        # Listen-and-repeat steps (intro) offer per-item audio, so a tappable
        # Listen button replaces the "audio being prepared" placeholder.
        self.assertTrue('data-lr-start' in body or 'onlenco-stage__pending' in body)

    def test_audio_placeholder_when_audio_rejected(self):
        self._attach_audio(self._intro_script(), "rejected")
        body = self._body("intro")
        self.assertNotIn('class="onlenco-mega-player"', body)   # no unapproved player leaks
        # Listen-and-repeat steps (intro) offer per-item audio, so a tappable
        # Listen button replaces the "audio being prepared" placeholder.
        self.assertTrue('data-lr-start' in body or 'onlenco-stage__pending' in body)

    def test_audio_placeholder_when_approved_file_missing(self):
        # Approved status but NO file -> is_student_visible False -> placeholder, no crash.
        s = self._intro_script()
        s.generation_status = "approved"
        s.generated_audio = ""
        s.save()
        body = self._body("intro")
        self.assertNotIn('class="onlenco-mega-player"', body)   # no unapproved player leaks
        # Listen-and-repeat steps (intro) offer per-item audio, so a tappable
        # Listen button replaces the "audio being prepared" placeholder.
        self.assertTrue('data-lr-start' in body or 'onlenco-stage__pending' in body)


class ScrubInternalLessonTextTests(TestCase):
    def setUp(self):
        from courses.models import Course, CourseLevel
        level = CourseLevel.objects.create(code="A1", name="A1", order=1)
        self.course = Course.objects.create(title="C", slug="c", level=level, status="published")
        self.lesson = Lesson.objects.create(
            course=self.course, title="L1", order=1, status="published",
            content_html="<p>Real content.</p>\n{# Phase 9.5 — Visual placeholder for steps with associated LessonImagePrompt. NEVER renders the raw prompt. #}\n<p>More.</p>",
            content_ar="محتوى حقيقي. Phase 9.5 ملاحظة داخلية",
        )

    def test_scrub_internal_lesson_text_command_is_idempotent(self):
        call_command("scrub_internal_lesson_text", "--confirm", stdout=StringIO())
        self.lesson.refresh_from_db()
        self.assertNotIn("Phase 9.5", self.lesson.content_html)
        self.assertNotIn("{#", self.lesson.content_html)
        self.assertIn("Real content.", self.lesson.content_html)   # educational content kept
        self.assertNotIn("Phase 9.5", self.lesson.content_ar)
        snapshot = self.lesson.content_html
        # Second run changes nothing.
        out = StringIO()
        call_command("scrub_internal_lesson_text", "--confirm", stdout=out)
        self.lesson.refresh_from_db()
        self.assertEqual(self.lesson.content_html, snapshot)
        self.assertIn("0 lesson(s) were scrubbed", out.getvalue())

    def test_scrub_command_does_not_change_lesson_status(self):
        before = self.lesson.status
        call_command("scrub_internal_lesson_text", "--confirm", stdout=StringIO())
        self.lesson.refresh_from_db()
        self.assertEqual(self.lesson.status, before)

    def test_scrub_dry_run_changes_nothing(self):
        call_command("scrub_internal_lesson_text", "--dry-run", stdout=StringIO())
        self.lesson.refresh_from_db()
        self.assertIn("Phase 9.5", self.lesson.content_html)   # untouched in dry-run


class ApproveMediaWithFilesTests(TestCase):
    def setUp(self):
        from courses.models import Course, CourseLevel, LessonAudioScript
        level = CourseLevel.objects.create(code="A1", name="A1", order=1)
        course = Course.objects.create(title="C", slug="c", level=level, status="published")
        self.lesson = Lesson.objects.create(course=course, title="L", order=1, status="published")
        self.pending = LessonAudioScript.objects.create(
            lesson=self.lesson, script_type="intro", script_text="hi",
            generated_audio="lessons/audio/x.mp3", generation_status="pending_generation")
        self.rejected = LessonAudioScript.objects.create(
            lesson=self.lesson, script_type="vocabulary", script_text="hi",
            generated_audio="lessons/audio/y.mp3", generation_status="rejected")
        self.nofile = LessonAudioScript.objects.create(
            lesson=self.lesson, script_type="examples", script_text="hi",
            generated_audio="", generation_status="pending_generation")

    def test_approves_only_pending_with_file(self):
        call_command("approve_media_with_files", "--confirm", stdout=StringIO())
        self.pending.refresh_from_db()
        self.rejected.refresh_from_db()
        self.nofile.refresh_from_db()
        self.assertEqual(self.pending.generation_status, "approved")
        self.assertEqual(self.rejected.generation_status, "rejected")        # left alone
        self.assertEqual(self.nofile.generation_status, "pending_generation")  # no file -> skip

    def test_does_not_change_lesson_status(self):
        before = self.lesson.status
        call_command("approve_media_with_files", "--confirm", stdout=StringIO())
        self.lesson.refresh_from_db()
        self.assertEqual(self.lesson.status, before)

    def test_idempotent(self):
        call_command("approve_media_with_files", "--confirm", stdout=StringIO())
        out = StringIO()
        call_command("approve_media_with_files", "--confirm", stdout=out)
        self.assertIn("approved=0", out.getvalue())

    def test_dry_run_changes_nothing(self):
        call_command("approve_media_with_files", "--dry-run", stdout=StringIO())
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.generation_status, "pending_generation")


class InspectLessonMediaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        _seed_all()
        cls.course, cls.lesson, cls.quiz = _get_lesson_quiz()

    def test_inspect_lesson_media_reports_all_steps(self):
        out = StringIO()
        call_command("inspect_lesson_media", "--lesson-id", str(self.lesson.pk), stdout=out)
        text = out.getvalue()
        self.assertIn("intro", text)
        self.assertIn("audio", text)

    def test_inspect_lesson_media_reports_missing_audio_reason(self):
        out = StringIO()
        call_command("inspect_lesson_media", "--lesson-id", str(self.lesson.pk), "--step", "intro", stdout=out)
        text = out.getvalue()
        # No generated audio in a fresh seed -> not_generated / needs_review surfaced.
        self.assertTrue(("not_generated" in text) or ("needs_review" in text) or ("pending" in text))

    def test_inspect_lesson_media_does_not_modify_data(self):
        before = self.lesson.audio_scripts.count()
        call_command("inspect_lesson_media", "--lesson-id", str(self.lesson.pk), stdout=StringIO())
        self.assertEqual(self.lesson.audio_scripts.count(), before)
