"""Prompt 12B.1 — Minor Content Fix Pass + Legacy Cleanup gate tests."""
from __future__ import annotations

import re

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from platform_admin import permissions as control_perms

from courses.models import (
    CourseUnit, Lesson, LessonImagePrompt, LessonReviewEvent,
)
from courses.services import content_quality_checker as q
from learning_core.models import Skill

User = get_user_model()
SLUG = "onlenco-beginner"
BRAND_RE = re.compile(r"(dk\b|duolingo|\bowl\b)", re.IGNORECASE)


def _pending():
    return Lesson.objects.filter(course__slug=SLUG, status="pending_review")


class Prompt12B1Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_platform_roles", verbosity=0)
        call_command("seed_learning_skills", verbosity=0)
        call_command("seed_super_lesson_01", verbosity=0)
        call_command("seed_beginner_48_topics", "--confirm", verbosity=0)
        for L in _pending():
            q.save_quality_result(L, q.check_lesson_quality(L))

        course = _pending().first().course
        # Create legacy BROKEN published lessons (no quiz/content → score 0).
        unit = CourseUnit.objects.create(course=course, title="Legacy", order=90)
        cls.legacy_ids = []
        for i in range(3):
            L = Lesson.objects.create(
                course=course, unit=unit, order=90 + i,
                title=f"Legacy Broken {i}", status="published", is_active=True,
                cefr_level="A1",
            )
            cls.legacy_ids.append(L.id)
        cls.gold = Lesson.objects.get(course__slug=SLUG, order=1)

    def _teacher(self):
        u = User.objects.create_user(username="t121@x.com", password="pw12345!")
        g, _ = Group.objects.get_or_create(name=control_perms.GROUP_TEACHER)
        u.groups.add(g)
        return u

    def _student(self):
        return User.objects.create_user(username="s121@x.com", password="pw12345!")

    # ---------- Brand fix ----------
    def test_topics_26_33_image_prompts_no_brand_names(self):
        prompts = LessonImagePrompt.objects.filter(
            lesson__in=_pending().filter(order__gte=26, order__lte=33))
        self.assertTrue(prompts.exists())
        for ip in prompts:
            self.assertIsNone(BRAND_RE.search(ip.prompt),
                              f"brand token in T?? prompt: {ip.prompt!r}")

    def test_image_prompts_keep_original_onlenco_style_instruction(self):
        for ip in LessonImagePrompt.objects.filter(
                lesson__in=_pending().filter(order__gte=26, order__lte=33)):
            self.assertIn("original onlenco", ip.prompt.lower())

    def test_quality_checker_no_brand_risk_for_topics_26_33(self):
        for L in _pending().filter(order__gte=26, order__lte=33):
            codes = [f["code"] for f in q.check_lesson_quality(L)["flags"]]
            self.assertNotIn("brand_risk", codes)

    def test_no_media_generated_during_12b1(self):
        # No image/audio FILE was produced — prompts stay un-generated.
        self.assertFalse(
            LessonImagePrompt.objects.filter(lesson__in=_pending())
            .exclude(generated_image="").exists())
        self.assertFalse(
            LessonImagePrompt.objects.filter(lesson__in=_pending(), is_generated=True).exists())

    # ---------- Skill fix ----------
    def test_added_mistake_correction_or_error_correction_skill_exists(self):
        self.assertTrue(Skill.objects.filter(code="error_correction").exists())

    def test_no_general_beginner_fallback_skills_in_topics_02_48(self):
        for L in _pending():
            quiz = getattr(L, "quiz", None)
            if not quiz:
                continue
            for ques in quiz.questions.all():
                skills = (ques.metadata or {}).get("skills") or []
                self.assertNotIn("general_beginner", skills,
                                 f"fallback skill on lesson {L.order} q{ques.order}")

    def test_all_question_skills_exist_after_12b1(self):
        valid = set(Skill.objects.exclude(code="").values_list("code", flat=True))
        for L in _pending():
            quiz = getattr(L, "quiz", None)
            if not quiz:
                continue
            for ques in quiz.questions.all():
                for code in (ques.metadata or {}).get("skills") or []:
                    self.assertIn(code, valid, f"unknown skill {code} on q{ques.order}")

    def test_quality_checker_no_fallback_skill_warnings_after_12b1(self):
        for L in _pending():
            codes = [f["code"] for f in q.check_lesson_quality(L)["flags"]]
            self.assertNotIn("fallback_skill", codes)

    # ---------- Legacy cleanup ----------
    def test_legacy_cleanup_command_dry_run_does_not_modify(self):
        call_command("archive_legacy_broken_beginner_lessons", "--dry-run", verbosity=0)
        for lid in self.legacy_ids:
            self.assertEqual(Lesson.objects.get(id=lid).status, "published")

    def test_legacy_cleanup_command_confirm_archives(self):
        call_command("archive_legacy_broken_beginner_lessons", "--confirm", verbosity=0)
        for lid in self.legacy_ids:
            self.assertEqual(Lesson.objects.get(id=lid).status, "archived")

    def test_legacy_broken_published_lessons_are_archived(self):
        call_command("archive_legacy_broken_beginner_lessons", "--confirm", verbosity=0)
        self.assertFalse(
            Lesson.objects.filter(id__in=self.legacy_ids, status="published").exists())

    def test_legacy_cleanup_does_not_touch_topic_01_gold(self):
        call_command("archive_legacy_broken_beginner_lessons", "--confirm", verbosity=0)
        self.gold.refresh_from_db()
        self.assertEqual(self.gold.status, "published")
        self.assertEqual(self.gold.order, 1)
        self.assertEqual(self.gold.quiz.questions.count(), 10)

    def test_legacy_cleanup_does_not_touch_pending_review_topics(self):
        call_command("archive_legacy_broken_beginner_lessons", "--confirm", verbosity=0)
        self.assertEqual(_pending().count(), 47)

    def test_lesson_review_event_created_for_archived_legacy_lessons(self):
        call_command("archive_legacy_broken_beginner_lessons", "--confirm", verbosity=0)
        for lid in self.legacy_ids:
            self.assertTrue(
                LessonReviewEvent.objects.filter(lesson_id=lid, action="archive").exists())

    def test_student_cannot_access_archived_legacy_lessons(self):
        call_command("archive_legacy_broken_beginner_lessons", "--confirm", verbosity=0)
        self.client.force_login(self._student())
        lid = self.legacy_ids[0]
        course_id = Lesson.objects.get(id=lid).course_id
        resp = self.client.get(reverse("courses:lesson_detail",
                                       kwargs={"course_pk": course_id, "lesson_pk": lid}))
        self.assertNotEqual(resp.status_code, 200)

    def test_teacher_can_still_review_archived_legacy_lessons_if_supported(self):
        call_command("archive_legacy_broken_beginner_lessons", "--confirm", verbosity=0)
        self.client.force_login(self._teacher())
        resp = self.client.get(
            reverse("teacher_portal:content_review_detail", args=[self.legacy_ids[0]]))
        self.assertEqual(resp.status_code, 200)
