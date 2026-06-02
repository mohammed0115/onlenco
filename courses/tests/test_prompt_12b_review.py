"""Prompt 12B — Human Review QA Pass gate tests.

Seeds the real Beginner content into the test DB, runs the quality checker,
and verifies the review/gate invariants. NOTHING is published here.
"""
from __future__ import annotations

import os

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from platform_admin import permissions as control_perms

from courses.models import Lesson, LessonReviewEvent
from courses.services import content_quality_checker as q

User = get_user_model()
SLUG = "onlenco-beginner"


def _pending():
    return Lesson.objects.filter(course__slug=SLUG, status="pending_review")


class Prompt12BReviewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_platform_roles", verbosity=0)
        call_command("seed_learning_skills", verbosity=0)
        call_command("seed_super_lesson_01", verbosity=0)
        call_command("seed_beginner_48_topics", "--confirm", verbosity=0)
        # Persist quality results (what check_generated_content_quality --save does).
        for L in _pending():
            q.save_quality_result(L, q.check_lesson_quality(L))
        cls.topic = _pending().order_by("order").first()  # Topic 02

    # --- users -----------------------------------------------------------
    def _teacher(self):
        u = User.objects.create_user(username="t12b@x.com", password="pw12345!")
        g, _ = Group.objects.get_or_create(name=control_perms.GROUP_TEACHER)
        u.groups.add(g)
        return u

    def _student(self):
        return User.objects.create_user(username="s12b@x.com", password="pw12345!")

    # --- invariants ------------------------------------------------------
    def test_all_pending_topics_have_review_status(self):
        self.assertEqual(_pending().count(), 47)
        self.assertFalse(_pending().exclude(status="pending_review").exists())

    def test_quality_scores_saved_for_all_pending_topics(self):
        for L in _pending():
            self.assertIsNotNone(L.quality_score)
            self.assertIsInstance(L.quality_flags, list)

    def test_no_topic_published_by_prompt_12b(self):
        # The 47 reviewed topics must all remain pending_review.
        self.assertEqual(_pending().count(), 47)
        self.assertFalse(
            Lesson.objects.filter(course__slug=SLUG, status="published", order__gte=2)
            .filter(id__in=[t.id for t in _pending()]).exists()
        )

    def test_topic_01_gold_reference_unchanged(self):
        gold = Lesson.objects.get(course__slug=SLUG, order=1)
        self.assertEqual(gold.title, "Introducing Yourself")
        self.assertEqual(gold.status, "published")
        self.assertEqual(gold.quiz.questions.count(), 10)

    def test_review_event_created_for_quality_review(self):
        ev = LessonReviewEvent.objects.create(
            lesson=self.topic, action="quality_check",
            from_status=self.topic.status, quality_score=self.topic.quality_score,
            metadata={"phase": "12b", "classification": "approved_ready"},
        )
        self.topic.refresh_from_db()
        self.assertEqual(self.topic.status, "pending_review")  # unchanged
        self.assertEqual(ev.action, "quality_check")
        self.assertTrue(
            LessonReviewEvent.objects.filter(lesson=self.topic, action="quality_check").exists()
        )

    def test_review_notes_can_be_saved_for_topic(self):
        ev = LessonReviewEvent.objects.create(
            lesson=self.topic, action="note_added", note="12B reviewer note.",
        )
        self.assertEqual(
            LessonReviewEvent.objects.get(pk=ev.pk).note, "12B reviewer note."
        )

    def test_fallback_skill_topics_can_be_filtered(self):
        # Verifies the FILTER mechanism (not that fallbacks exist — Prompt 12B.1
        # removed them all). Inject one fallback skill, then confirm the filter
        # surfaces exactly that topic.
        target = self.topic
        ques = target.quiz.questions.order_by("order").first()
        md = dict(ques.metadata or {})
        md["skills"] = ["general_beginner"]
        ques.metadata = md
        ques.save(update_fields=["metadata"])

        hits = []
        for L in _pending():
            quiz = getattr(L, "quiz", None)
            if not quiz:
                continue
            for q_ in quiz.questions.all():
                sk = [s.lower() for s in ((q_.metadata or {}).get("skills") or [])]
                if "general_beginner" in sk:
                    hits.append(L.order)
                    break
        self.assertEqual(hits, [target.order])

    def test_student_still_cannot_access_pending_topics(self):
        self.client.force_login(self._student())
        url = reverse("courses:lesson_detail",
                      kwargs={"course_pk": self.topic.course_id, "lesson_pk": self.topic.id})
        resp = self.client.get(url)
        self.assertNotEqual(resp.status_code, 200)

    def test_teacher_can_preview_pending_topic(self):
        self.client.force_login(self._teacher())
        resp = self.client.get(
            reverse("teacher_portal:content_review_detail", args=[self.topic.id])
        )
        self.assertEqual(resp.status_code, 200)

    def test_quality_flags_visible_in_review_dashboard(self):
        # The dashboard re-computes flags LIVE. After Prompt 12B.1 the real
        # topics are clean (score 100), so create a deliberately-broken lesson
        # (no quiz/checklist/media) and confirm its live flags render.
        broken = Lesson.objects.create(
            course=self.topic.course, unit=self.topic.unit, order=95,
            title="Broken QA Fixture", status="pending_review", cefr_level="A1",
        )
        self.client.force_login(self._teacher())
        resp = self.client.get(
            reverse("teacher_portal:content_review_detail", args=[broken.id])
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        self.assertIn("data-flag-code", body)
        self.assertIn("no_quiz", body)

    def test_manual_review_classification_report_exists(self):
        path = os.path.join(settings.BASE_DIR,
                            "docs", "PROMPT_12B_HUMAN_REVIEW_QA_PASS_REPORT.md")
        self.assertTrue(os.path.exists(path))

    def test_ai_usage_not_bypassed_during_review_if_ai_used(self):
        from ai_usage.models import AIUsageLog
        before = AIUsageLog.objects.count()
        # The quality checker is deterministic and must make NO AI call.
        q.check_lesson_quality(self.topic)
        self.assertEqual(AIUsageLog.objects.count(), before)
