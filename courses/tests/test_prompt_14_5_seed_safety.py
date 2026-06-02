"""Prompt 14.5 — seed_beginner_48_topics status-preservation safety tests."""
from __future__ import annotations

from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from platform_admin import permissions as control_perms

from accounts.models import APPROVAL_APPROVED, APPROVAL_PENDING_ADMIN
from courses.models import CourseUnit, Lesson

User = get_user_model()
SLUG = "onlenco-beginner"
BATCH = [2, 3, 4, 5, 6]


def _new(order):
    return Lesson.objects.filter(course__slug=SLUG, order=order).exclude(status="archived").first()


def _seed(**kw):
    call_command("seed_beginner_48_topics", "--confirm", stdout=StringIO(), **kw)


class Prompt145SeedSafetyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_platform_roles", verbosity=0)
        call_command("seed_learning_skills", verbosity=0)
        call_command("seed_super_lesson_01", verbosity=0)
        call_command("seed_beginner_48_topics", "--confirm", verbosity=0)
        cls.admin = User.objects.create_superuser("p145@x.com", "p145@x.com", "pw12345!")
        # Reach the real Prompt-14 production-like state: 02-06 approved → published.
        call_command("approve_teacher_batch", "--course", SLUG, "--topics", "2-6",
                     "--confirm", "--actor", cls.admin.username, verbosity=0)
        call_command("publish_teacher_batch", "--course", SLUG, "--topics", "2-6",
                     "--confirm", "--actor", cls.admin.username, verbosity=0)
        # An archived legacy lesson (separate unit) — must stay archived.
        course = _new(2).course
        unit = CourseUnit.objects.create(course=course, title="Legacy", order=90)
        cls.legacy = Lesson.objects.create(course=course, unit=unit, order=95,
                                           title="Legacy Broken", status="archived",
                                           is_active=False, cefr_level="A1")
        cls.gold = Lesson.objects.get(course__slug=SLUG, order=1)

    def _student(self, username, status=APPROVAL_APPROVED):
        u = User.objects.create_user(username=username, email=username, password="pw12345!")
        p = u.profile
        p.role = "student"; p.email_verified = True; p.approval_status = status
        p.save()
        return u

    def _teacher(self):
        u = User.objects.create_user("t145@x.com", "t145@x.com", "pw12345!")
        g, _ = Group.objects.get_or_create(name=control_perms.GROUP_TEACHER)
        u.groups.add(g)
        return u

    # ---------- status preservation ----------
    def test_seed_beginner_48_topics_preserves_published_status(self):
        _seed()
        for o in BATCH:
            self.assertEqual(_new(o).status, "published")

    def test_seed_beginner_48_topics_preserves_approved_status(self):
        # Make Topic 07 approved, then reseed → must stay approved.
        from courses.services import lesson_review_workflow as wf
        wf.approve(actor=self.admin, lesson=_new(7), note="x")
        _seed()
        self.assertEqual(_new(7).status, "approved")

    def test_seed_beginner_48_topics_preserves_archived_status(self):
        _seed()
        self.legacy.refresh_from_db()
        self.assertEqual(self.legacy.status, "archived")

    def test_seed_beginner_48_topics_does_not_clear_published_at(self):
        before = {o: _new(o).published_at for o in BATCH}
        _seed()
        for o in BATCH:
            self.assertEqual(_new(o).published_at, before[o])
            self.assertIsNotNone(_new(o).published_at)

    def test_seed_beginner_48_topics_does_not_clear_approved_fields(self):
        before = {o: (_new(o).approved_by_id, _new(o).approved_at) for o in BATCH}
        _seed()
        for o in BATCH:
            L = _new(o)
            self.assertEqual((L.approved_by_id, L.approved_at), before[o])
            self.assertIsNotNone(L.approved_by_id)

    def test_seed_beginner_48_topics_preserves_topic_01_gold(self):
        before = (self.gold.status, self.gold.quiz.questions.count(), self.gold.content_html)
        _seed()
        self.gold.refresh_from_db()
        self.assertEqual((self.gold.status, self.gold.quiz.questions.count(),
                          self.gold.content_html), before)

    # ---------- updatable behaviour ----------
    def test_seed_beginner_48_topics_updates_pending_review_topics(self):
        L = _new(20)
        L.content_html = "STALE"
        L.save(update_fields=["content_html"])
        _seed()
        L.refresh_from_db()
        self.assertNotEqual(L.content_html, "STALE")  # refreshed
        self.assertEqual(L.status, "pending_review")  # status kept

    def test_seed_beginner_48_topics_creates_missing_topic_as_pending_review(self):
        L = _new(30)
        unit = L.unit
        L.delete()
        _seed()
        recreated = Lesson.objects.filter(course__slug=SLUG, unit=unit, order=30).first()
        self.assertIsNotNone(recreated)
        self.assertEqual(recreated.status, "pending_review")

    def test_seed_beginner_48_topics_confirm_no_status_regression_after_prompt14(self):
        from collections import Counter
        before = dict(Counter(Lesson.objects.filter(course__slug=SLUG).values_list("status", flat=True)))
        _seed()
        after = dict(Counter(Lesson.objects.filter(course__slug=SLUG).values_list("status", flat=True)))
        self.assertEqual(before, after)

    def test_seed_single_topic_preserves_status(self):
        _seed(topic=2)
        self.assertEqual(_new(2).status, "published")

    def test_seed_dry_run_changes_nothing(self):
        from collections import Counter
        before = dict(Counter(Lesson.objects.filter(course__slug=SLUG).values_list("status", flat=True)))
        call_command("seed_beginner_48_topics", "--dry-run", stdout=StringIO())
        after = dict(Counter(Lesson.objects.filter(course__slug=SLUG).values_list("status", flat=True)))
        self.assertEqual(before, after)

    def test_seed_command_reports_skipped_published_and_archived(self):
        out = StringIO()
        call_command("seed_beginner_48_topics", "--confirm", stdout=out)
        text = out.getvalue()
        self.assertIn("skipped_published=5", text)
        self.assertIn("No review/publish status changed", text)

    def test_seed_reset_status_requires_explicit_flags(self):
        # --reset-status without ack must error (never silently unpublish).
        with self.assertRaises(CommandError):
            call_command("seed_beginner_48_topics", "--confirm", "--reset-status",
                         "--topic", "2", stdout=StringIO())
        self.assertEqual(_new(2).status, "published")  # unchanged

    # ---------- visibility survives reseed ----------
    @override_settings(ONLENCO_STUDENT_APPROVAL_REQUIRED=True)
    def test_published_batch_1_remains_visible_after_reseed(self):
        _seed()
        self.client.force_login(self._student("vis@x.com"))
        L = _new(2)
        resp = self.client.get(reverse("courses:lesson_detail",
                                       kwargs={"course_pk": L.course_id, "lesson_pk": L.id}))
        self.assertEqual(resp.status_code, 200)

    def test_student_access_to_topics_02_06_survives_reseed(self):
        from courses.services.student_flow import published_lesson_queryset
        _seed()
        visible = set(published_lesson_queryset().filter(course__slug=SLUG)
                      .values_list("order", flat=True))
        for o in BATCH:
            self.assertIn(o, visible)

    def test_topics_07_48_remain_pending_review_after_reseed(self):
        _seed()
        self.assertEqual(
            Lesson.objects.filter(course__slug=SLUG, status="pending_review").count(), 42)

    def test_archived_legacy_lessons_remain_archived_after_reseed(self):
        _seed()
        self.legacy.refresh_from_db()
        self.assertEqual(self.legacy.status, "archived")

    # ---------- regression ----------
    def test_publish_batch_1_still_works(self):
        # Roll 02 back to approved, reseed (stays approved), then republish.
        from courses.services import lesson_review_workflow as wf
        wf.unpublish(actor=self.admin, lesson=_new(2), note="x")
        _seed()
        self.assertEqual(_new(2).status, "approved")
        call_command("publish_teacher_batch", "--course", SLUG, "--topics", "2-2",
                     "--confirm", "--actor", self.admin.username, stdout=StringIO())
        self.assertEqual(_new(2).status, "published")

    def test_unpublish_batch_1_still_works(self):
        call_command("unpublish_teacher_batch", "--course", SLUG, "--topics", "2-2",
                     "--confirm", "--actor", self.admin.username, stdout=StringIO())
        self.assertEqual(_new(2).status, "approved")

    def test_review_dashboard_status_counts_after_reseed(self):
        _seed()
        self.client.force_login(self._teacher())
        resp = self.client.get(reverse("teacher_portal:content_review_list") + "?status=published")
        self.assertEqual(resp.status_code, 200)

    @override_settings(ONLENCO_STUDENT_APPROVAL_REQUIRED=True)
    def test_student_approval_gate_still_blocks_pending_students(self):
        _seed()
        self.client.force_login(self._student("pend145@x.com", status=APPROVAL_PENDING_ADMIN))
        resp = self.client.get(reverse("dashboard"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/account/pending-approval", resp["Location"])

    def test_topic_01_gold_reference_unchanged(self):
        _seed()
        self.gold.refresh_from_db()
        self.assertEqual(self.gold.status, "published")
        self.assertEqual(self.gold.order, 1)
