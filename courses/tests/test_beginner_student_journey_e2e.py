"""Prompt 18.4A — Beginner A0 student journey E2E smoke.

Walks the real student path with the Django test client (no browser tooling
in this project): dashboard -> beginner course -> first lesson (approved media
only) -> mark progress -> Daily Quiz (backend grading, correctness score) ->
Weekly Review gate card. Also covers routing guards (logout/login does not
re-force placement; A0 placement recommends the beginner levels).

Smoke/QA only — no new features, no media regen, no migration. Reuses the
existing flows (seed command, mark_lesson_complete view, /daily/ endpoints,
weekly_review_gate read-only service).
"""
from __future__ import annotations

import json

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts import onboarding as onboarding_lib
from courses.models import Course, CourseLessonProgress, Lesson
from courses.services import student_flow

User = get_user_model()


@override_settings(AXES_ENABLED=False)
class BeginnerStudentJourneyE2ETests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_onlenco_beginner_48_units", "--quiet")
        cls.course = Course.objects.get(slug="onlenco-beginner")
        # Journey opens any lesson regardless of the daily drip unlock.
        cls.course.drip_enabled = False
        cls.course.save(update_fields=["drip_enabled"])
        cls.first_unit = cls.course.units.order_by("order").first()
        cls.unit_lessons = list(
            Lesson.objects.filter(course=cls.course, unit=cls.first_unit)
            .order_by("order")
        )

    def setUp(self):
        self.user = User.objects.create_user(username="journey@x.com", password="pw")
        # Real beginner onboarding: A0, beginner_start path, onboarding_completed.
        onboarding_lib.complete_beginner_onboarding(self.user)
        p = self.user.profile
        p.subscription_status = "active"
        p.subscription_expires_at = timezone.now() + timezone.timedelta(days=30)
        p.save()
        self.client.login(username="journey@x.com", password="pw")

    # --- helpers -----------------------------------------------------------
    def _lesson(self, book_unit):
        return Lesson.objects.get(course=self.course, book_unit_number=book_unit)

    def _approve_image(self, lesson, ptype, status="approved"):
        p = lesson.image_prompts.filter(prompt_type=ptype).first()
        p.generated_image.save(f"{ptype}{lesson.order}.png", ContentFile(b"img"), save=False)
        p.is_generated = True
        p.generation_status = status
        p.save()
        return p

    def _approve_audio(self, lesson, stype, status="approved"):
        s = lesson.audio_scripts.filter(script_type=stype).first()
        s.generated_audio.save(f"{stype}{lesson.order}.mp3", ContentFile(b"aud"), save=False)
        s.is_generated = True
        s.generation_status = status
        s.save()
        return s

    def _detail_url(self):
        return reverse("courses:course_detail", args=[self.course.pk])

    def _step_url(self, lesson, kind):
        return reverse("courses:lesson_step", args=[self.course.pk, lesson.pk, kind])

    def _daily_plan(self):
        from daily_learning.models import DailyLearningPlan
        return DailyLearningPlan.objects.get(user=self.user, date=timezone.localdate())

    # --- 1. dashboard ------------------------------------------------------
    def test_a0_student_opens_dashboard(self):
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)

    # --- 2. beginner course ------------------------------------------------
    def test_a0_student_opens_beginner_course(self):
        r = self.client.get(self._detail_url())
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.context["is_a0_world"])      # rendered as A0 world
        self.assertIsNotNone(r.context["a0_world"])

    # --- 3. first lesson ---------------------------------------------------
    def test_a0_student_opens_first_lesson(self):
        lesson = self._lesson(1)
        url = reverse("courses:lesson_detail", args=[self.course.pk, lesson.pk])
        self.assertEqual(self.client.get(url).status_code, 200)

    # --- 4. lesson page shows only approved media --------------------------
    def test_lesson_step_shows_approved_cover_and_audio(self):
        lesson = self._lesson(1)
        cover = self._approve_image(lesson, "cover")
        html = self.client.get(self._step_url(lesson, "intro")).content.decode()
        self.assertIn(cover.generated_image.url, html)
        # Listen-repeat steps (intro/examples) use natural per-item clips; the
        # combined recording plays on the dialogue step (no per-item content).
        audio = self._approve_audio(lesson, "dialogue")
        dlg = self.client.get(self._step_url(lesson, "dialogue")).content.decode()
        self.assertIn(audio.generated_audio.url, dlg)

    def test_lesson_step_hides_pending_media(self):
        lesson = self._lesson(6)
        pending = self._approve_image(lesson, "vocabulary", status="needs_review")
        html = self.client.get(self._step_url(lesson, "vocabulary")).content.decode()
        self.assertNotIn(pending.generated_image.url, html)   # not student-visible
        self.assertNotIn("needs_review", html)

    # --- 5. progress -------------------------------------------------------
    def test_completing_lesson_creates_progress(self):
        lesson = self._lesson(1)
        url = reverse("courses:mark_lesson_complete", args=[self.course.pk, lesson.pk])
        r = self.client.post(url)
        self.assertIn(r.status_code, (302, 303))
        prog = CourseLessonProgress.objects.get(user=self.user, lesson=lesson)
        self.assertTrue(prog.video_completed)

    # --- 6-8. Daily Quiz ---------------------------------------------------
    def test_daily_quiz_opens_for_a0(self):
        self.assertEqual(self.client.get("/daily/").status_code, 200)

    def test_daily_quiz_answer_flow_backend_grading(self):
        self.client.get("/daily/")
        item = self._daily_plan().items.filter(item_type="quiz").first()
        self.assertIsNotNone(item)
        r_ok = self.client.post(
            f"/daily/items/{item.id}/complete/",
            data=json.dumps({"answer": item.correct_answer}),
            content_type="application/json")
        self.assertTrue(r_ok.json()["is_correct"])
        other = self._daily_plan().items.filter(item_type="quiz").exclude(id=item.id).first()
        if other:
            r_bad = self.client.post(
                f"/daily/items/{other.id}/complete/",
                data=json.dumps({"answer": "definitely-wrong-zz"}),
                content_type="application/json")
            self.assertFalse(r_bad.json()["is_correct"])
        # Server never leaks the expected answer back to the client.
        self.assertNotIn("expected", r_ok.json())

    def test_daily_quiz_score_is_correctness_based(self):
        # The real A0 plan has a single gradable quiz. Grading it WRONG must
        # yield score 0 — a completion-based score would be > 0 once the item
        # is marked done. This proves the score follows correctness, not
        # completion. (The mixed 50%% case is covered in the grading suite.)
        from daily_learning.services import daily_grading, daily_progress_service
        self.client.get("/daily/")
        plan = self._daily_plan()
        quiz = plan.items.filter(item_type="quiz").first()
        self.assertIsNotNone(quiz)
        grade = daily_grading.grade_item(quiz, {"answer": "definitely-wrong-zz"})
        self.assertFalse(grade["is_correct"])
        daily_progress_service.mark_item_complete(quiz, grade=grade)
        res = daily_progress_service.complete_plan(plan, force=True)
        self.assertEqual(res.score, 0.0)

    # --- 9-10. Weekly Review gate -----------------------------------------
    def _complete_unit(self):
        for le in self.unit_lessons[:3]:
            CourseLessonProgress.objects.create(
                user=self.user, lesson=le, completed_at=timezone.now())

    def test_weekly_card_hidden_before_three_lessons(self):
        html = self.client.get(self._detail_url()).content.decode()
        self.assertNotIn("weekly-review-card", html)

    def test_weekly_card_visible_and_safe_after_three_lessons(self):
        self._complete_unit()
        html = self.client.get(self._detail_url()).content.decode()
        self.assertIn("weekly-review-card", html)
        # Safe gate: disabled CTA, no live route inside the card block.
        card = html.split("weekly-review-card", 1)[1].split("</section>", 1)[0]
        self.assertIn("disabled", card)
        self.assertNotIn("href", card)

    def test_weekly_card_does_not_change_progress(self):
        self._complete_unit()
        before = CourseLessonProgress.objects.count()
        self.client.get(self._detail_url())
        self.assertEqual(CourseLessonProgress.objects.count(), before)

    # --- 11. logout/login does not re-force placement ----------------------
    def test_logout_login_does_not_force_placement(self):
        self.client.logout()
        self.assertTrue(self.client.login(username="journey@x.com", password="pw"))
        for name in ("dashboard",):
            r = self.client.get(reverse(name))
            self.assertEqual(r.status_code, 200)
            self.assertNotIn("placement", r.get("Location", ""))
        # Beginner is already chosen — onboarding stays complete.
        self.user.refresh_from_db()
        self.assertFalse(onboarding_lib.needs_onboarding(self.user.profile))

    # --- 12. A0 placement recommends beginner ------------------------------
    def test_a0_routing_recommends_beginner(self):
        visible = student_flow.visible_level_codes_for_user(self.user)
        self.assertIn("A0", visible)            # beginner course's level is reachable
        self.assertEqual(self.course.level.code, "A0")
