"""Phase 11 — Human Review Workflow / Teacher Approval Dashboard.

Covers:
  * Quality checker — scoring, fallback warnings, forbidden types,
    audio underscores, brand risks, structural completeness.
  * Workflow state machine — every transition, permissions, audit rows.
  * Dashboard list + detail render (login + permission gates).
  * Student visibility — pending/approved hidden, only published shown.
  * Management command — run, save, fail-on-errors.
  * Gold Reference + earlier suites still pass.
"""
from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse

from courses.models import (
    Course, CourseEnrollment, Lesson, LessonAudioScript,
    LessonChecklist, LessonImagePrompt, LessonQuestion, LessonQuiz,
    LessonReviewEvent,
)
from courses.services import (
    content_quality_checker, lesson_review_workflow as workflow,
)
from courses.services.student_flow import published_lesson_queryset


User = get_user_model()


def _seed_world():
    call_command("seed_learning_skills", verbosity=0)
    call_command("seed_badge_definitions", verbosity=0)
    call_command("seed_super_lesson_01", verbosity=0)
    call_command("seed_beginner_48_topics", "--confirm", verbosity=0)


def _make_user(name, *, role=None) -> User:
    u = User.objects.create_user(
        username=name, password="pw", email=f"{name}@onlenco.test",
    )
    if hasattr(u, "profile"):
        u.profile.email_verified = True
        u.profile.subscription_status = "active"
        u.profile.preferred_language = "en"
        u.profile.save()
    if role == "teacher":
        group, _ = Group.objects.get_or_create(name="Teacher")
        u.groups.add(group)
    elif role == "admin":
        u.is_staff = True
        u.is_superuser = True
        u.save()
    return u


def _login(user):
    c = Client(SERVER_NAME="127.0.0.1")
    c.force_login(user)
    return c


# ---------------------------------------------------------------------------
# 1. Quality checker
# ---------------------------------------------------------------------------

class QualityCheckerTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        _seed_world()

    def test_topic_01_gold_reference_scores_high(self):
        t1 = Lesson.objects.get(course__slug="onlenco-beginner", order=1)
        result = content_quality_checker.check_lesson_quality(t1)
        self.assertGreaterEqual(result["score"], 85)
        self.assertTrue(result["passed"])
        # No errors.
        errors = [f for f in result["flags"] if f["severity"] == "error"]
        self.assertEqual(len(errors), 0)

    def test_quality_checker_flags_missing_section(self):
        t2 = Lesson.objects.get(course__slug="onlenco-beginner", order=2)
        # Break it by removing a required section.
        t2.content_html = '<section class="lesson-goal"><h2>x</h2></section>'
        t2.save(update_fields=["content_html"])
        result = content_quality_checker.check_lesson_quality(t2)
        codes = {f["code"] for f in result["flags"]}
        self.assertIn("missing_section", codes)

    def test_quality_checker_flags_missing_arabic(self):
        t = Lesson.objects.get(course__slug="onlenco-beginner", order=3)
        t.content_ar = ""
        t.save(update_fields=["content_ar"])
        result = content_quality_checker.check_lesson_quality(t)
        codes = {f["code"] for f in result["flags"]}
        self.assertIn("missing_arabic", codes)

    def test_quality_checker_flags_forbidden_type_in_a0(self):
        t = Lesson.objects.get(course__slug="onlenco-beginner", order=4)
        # Inject a forbidden type into the quiz.
        LessonQuestion.objects.filter(quiz=t.quiz, order=1).update(
            question_type="listen_and_type",
        )
        result = content_quality_checker.check_lesson_quality(t)
        codes = {f["code"] for f in result["flags"]}
        self.assertIn("forbidden_type_a0", codes)
        self.assertFalse(result["passed"])

    def test_quality_checker_flags_fallback_skill(self):
        t = Lesson.objects.get(course__slug="onlenco-beginner", order=5)
        q = t.quiz.questions.first()
        md = q.metadata or {}
        md["skills"] = ["general_beginner"]
        q.metadata = md
        q.save(update_fields=["metadata"])
        result = content_quality_checker.check_lesson_quality(t)
        codes = {f["code"] for f in result["flags"]}
        self.assertIn("fallback_skill", codes)

    def test_quality_checker_flags_audio_underscore(self):
        t = Lesson.objects.get(course__slug="onlenco-beginner", order=6)
        LessonAudioScript.objects.filter(lesson=t).first()
        LessonAudioScript.objects.filter(lesson=t, script_type="intro").update(
            script_text="Hello _learner_, welcome to lesson_one.",
        )
        result = content_quality_checker.check_lesson_quality(t)
        codes = {f["code"] for f in result["flags"]}
        self.assertIn("audio_has_underscore", codes)
        self.assertFalse(result["passed"])

    def test_quality_checker_flags_brand_risk(self):
        t = Lesson.objects.get(course__slug="onlenco-beginner", order=7)
        LessonImagePrompt.objects.filter(lesson=t, prompt_type="cover").update(
            prompt="A cute Duolingo owl waves hello in the morning.",
        )
        result = content_quality_checker.check_lesson_quality(t)
        codes = {f["code"] for f in result["flags"]}
        self.assertIn("brand_risk", codes)

    def test_quality_checker_requires_8_to_12_questions(self):
        t = Lesson.objects.get(course__slug="onlenco-beginner", order=8)
        # Delete all but 5 questions.
        ids = list(
            t.quiz.questions.order_by("order").values_list("pk", flat=True)
        )
        LessonQuestion.objects.filter(pk__in=ids[5:]).delete()
        result = content_quality_checker.check_lesson_quality(t)
        codes = {f["code"] for f in result["flags"]}
        self.assertIn("too_few_questions", codes)


# ---------------------------------------------------------------------------
# 2. Workflow state machine
# ---------------------------------------------------------------------------

class WorkflowTransitionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        _seed_world()
        cls.teacher = _make_user("teach-1", role="teacher")
        cls.admin = _make_user("admin-1", role="admin")

    def _lesson(self, order):
        return Lesson.objects.get(course__slug="onlenco-beginner", order=order)

    def test_start_review_changes_status(self):
        l = self._lesson(10)
        self.assertEqual(l.status, "pending_review")
        workflow.start_review(actor=self.teacher, lesson=l)
        l.refresh_from_db()
        self.assertEqual(l.status, "in_review")

    def test_start_review_writes_event(self):
        l = self._lesson(11)
        workflow.start_review(actor=self.teacher, lesson=l, note="kicking off")
        evt = LessonReviewEvent.objects.filter(lesson=l).first()
        self.assertEqual(evt.action, "start_review")
        self.assertEqual(evt.actor_id, self.teacher.pk)
        self.assertEqual(evt.note, "kicking off")

    def test_request_changes_requires_note(self):
        l = self._lesson(12)
        workflow.start_review(actor=self.teacher, lesson=l)
        with self.assertRaises(workflow.WorkflowError):
            workflow.request_changes(actor=self.teacher, lesson=l, note="")

    def test_request_changes_transitions(self):
        l = self._lesson(13)
        workflow.start_review(actor=self.teacher, lesson=l)
        workflow.request_changes(actor=self.teacher, lesson=l, note="please fix Q3")
        l.refresh_from_db()
        self.assertEqual(l.status, "changes_requested")

    def test_approve_clean_lesson_works(self):
        l = self._lesson(14)
        workflow.start_review(actor=self.teacher, lesson=l)
        workflow.approve(actor=self.teacher, lesson=l, note="LGTM")
        l.refresh_from_db()
        self.assertEqual(l.status, "approved")
        self.assertEqual(l.approved_by_id, self.teacher.pk)
        self.assertIsNotNone(l.approved_at)
        self.assertGreaterEqual(l.quality_score, 85)

    def test_approve_refuses_when_errors_present(self):
        l = self._lesson(15)
        # Break a section.
        l.content_html = "<p>nothing here</p>"
        l.save(update_fields=["content_html"])
        workflow.start_review(actor=self.teacher, lesson=l)
        with self.assertRaises(workflow.WorkflowError):
            workflow.approve(actor=self.teacher, lesson=l)

    def test_admin_override_can_force_approve(self):
        l = self._lesson(16)
        l.content_html = "<p>nothing here</p>"
        l.save(update_fields=["content_html"])
        workflow.start_review(actor=self.teacher, lesson=l)
        # Admin uses override=True
        workflow.approve(actor=self.admin, lesson=l, override=True)
        l.refresh_from_db()
        self.assertEqual(l.status, "approved")

    def test_publish_requires_approved(self):
        l = self._lesson(17)
        with self.assertRaises(workflow.WorkflowError):
            workflow.publish(actor=self.admin, lesson=l)

    def test_publish_makes_lesson_visible(self):
        l = self._lesson(18)
        workflow.start_review(actor=self.teacher, lesson=l)
        workflow.approve(actor=self.teacher, lesson=l)
        workflow.publish(actor=self.admin, lesson=l)
        l.refresh_from_db()
        self.assertEqual(l.status, "published")
        self.assertIsNotNone(l.published_at)
        # Visible via student queryset now.
        self.assertTrue(published_lesson_queryset().filter(pk=l.pk).exists())

    def test_unpublish_hides_again(self):
        l = self._lesson(19)
        workflow.start_review(actor=self.teacher, lesson=l)
        workflow.approve(actor=self.teacher, lesson=l)
        workflow.publish(actor=self.admin, lesson=l)
        workflow.unpublish(actor=self.admin, lesson=l, note="not yet")
        l.refresh_from_db()
        self.assertEqual(l.status, "approved")
        self.assertFalse(published_lesson_queryset().filter(pk=l.pk).exists())

    def test_add_note_does_not_change_status(self):
        l = self._lesson(20)
        before_status = l.status
        workflow.add_note(actor=self.teacher, lesson=l, note="quick note")
        l.refresh_from_db()
        self.assertEqual(l.status, before_status)
        evt = LessonReviewEvent.objects.filter(lesson=l, action="note_added").first()
        self.assertEqual(evt.note, "quick note")


# ---------------------------------------------------------------------------
# 3. Dashboard permissions + render
# ---------------------------------------------------------------------------

class DashboardPermissionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        _seed_world()
        cls.teacher = _make_user("teach-2", role="teacher")
        cls.admin = _make_user("admin-2", role="admin")
        cls.student = _make_user("stud-2")

    def test_anonymous_redirected(self):
        c = Client(SERVER_NAME="127.0.0.1")
        r = c.get(reverse("teacher_portal:content_review_list"),
                  HTTP_HOST="127.0.0.1")
        self.assertIn(r.status_code, {302, 401, 403})

    def test_student_cannot_access_dashboard(self):
        c = _login(self.student)
        r = c.get(reverse("teacher_portal:content_review_list"),
                  HTTP_HOST="127.0.0.1")
        self.assertEqual(r.status_code, 403)

    def test_teacher_can_access_dashboard(self):
        c = _login(self.teacher)
        r = c.get(reverse("teacher_portal:content_review_list"),
                  HTTP_HOST="127.0.0.1")
        self.assertEqual(r.status_code, 200)

    def test_admin_can_access_dashboard(self):
        c = _login(self.admin)
        r = c.get(reverse("teacher_portal:content_review_list"),
                  HTTP_HOST="127.0.0.1")
        self.assertEqual(r.status_code, 200)

    def test_dashboard_lists_pending_topics(self):
        c = _login(self.teacher)
        r = c.get(reverse("teacher_portal:content_review_list"),
                  HTTP_HOST="127.0.0.1")
        body = r.content.decode()
        # The 47 pending topics should appear.
        self.assertIn("pending_review", body)
        # At least the table marker.
        self.assertIn("data-review-table", body)

    def test_dashboard_filter_by_status(self):
        c = _login(self.teacher)
        r = c.get(reverse("teacher_portal:content_review_list") + "?status=published",
                  HTTP_HOST="127.0.0.1")
        self.assertEqual(r.status_code, 200)

    def test_detail_page_renders(self):
        l = Lesson.objects.get(course__slug="onlenco-beginner", order=2)
        c = _login(self.teacher)
        r = c.get(reverse("teacher_portal:content_review_detail", args=[l.pk]),
                  HTTP_HOST="127.0.0.1")
        self.assertEqual(r.status_code, 200)
        body = r.content.decode()
        self.assertIn(l.title, body)
        # Audit-trail panel + flags panel rendered.
        self.assertIn("data-review-detail", body)


# ---------------------------------------------------------------------------
# 4. Student visibility (the Human Review Gate)
# ---------------------------------------------------------------------------

class StudentVisibilityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        _seed_world()
        cls.course = Course.objects.get(slug="onlenco-beginner")
        cls.student = _make_user("stud-3")
        CourseEnrollment.objects.get_or_create(user=cls.student, course=cls.course)

    def test_student_cannot_access_pending_lesson(self):
        l = Lesson.objects.get(course=self.course, order=22)
        self.assertEqual(l.status, "pending_review")
        c = _login(self.student)
        r = c.get(reverse("courses:lesson_detail", args=[self.course.pk, l.pk]),
                  HTTP_HOST="127.0.0.1")
        self.assertEqual(r.status_code, 404)

    def test_student_cannot_access_approved_unpublished_lesson(self):
        teacher = _make_user("teach-vis", role="teacher")
        l = Lesson.objects.get(course=self.course, order=23)
        workflow.start_review(actor=teacher, lesson=l)
        workflow.approve(actor=teacher, lesson=l)
        l.refresh_from_db()
        self.assertEqual(l.status, "approved")
        c = _login(self.student)
        r = c.get(reverse("courses:lesson_detail", args=[self.course.pk, l.pk]),
                  HTTP_HOST="127.0.0.1")
        self.assertEqual(r.status_code, 404)

    def test_student_can_access_published_lesson(self):
        teacher = _make_user("teach-pub", role="teacher")
        admin = _make_user("admin-pub", role="admin")
        l = Lesson.objects.get(course=self.course, order=24)
        workflow.start_review(actor=teacher, lesson=l)
        workflow.approve(actor=teacher, lesson=l)
        workflow.publish(actor=admin, lesson=l)
        c = _login(self.student)
        r = c.get(reverse("courses:lesson_detail", args=[self.course.pk, l.pk]),
                  HTTP_HOST="127.0.0.1")
        self.assertEqual(r.status_code, 200)


# ---------------------------------------------------------------------------
# 5. Management command
# ---------------------------------------------------------------------------

class QualityCommandTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        _seed_world()

    def test_command_runs(self):
        # Just runs without raising.
        call_command("check_generated_content_quality",
                     "--topic=2", verbosity=0)

    def test_command_saves_scores(self):
        l = Lesson.objects.get(course__slug="onlenco-beginner", order=25)
        self.assertIsNone(l.quality_score)
        call_command("check_generated_content_quality",
                     "--topic=25", "--save", verbosity=0)
        l.refresh_from_db()
        self.assertIsNotNone(l.quality_score)
        self.assertGreaterEqual(l.quality_score, 85)
        # Audit event written.
        self.assertTrue(
            LessonReviewEvent.objects.filter(
                lesson=l, action="quality_check",
            ).exists()
        )

    def test_command_fail_on_errors(self):
        l = Lesson.objects.get(course__slug="onlenco-beginner", order=26)
        l.content_html = "<p>broken</p>"
        l.save(update_fields=["content_html"])
        with self.assertRaises(SystemExit):
            call_command("check_generated_content_quality",
                         "--topic=26", "--fail-on-errors", verbosity=0)


# ---------------------------------------------------------------------------
# 6. Regression — Gold Reference + earlier engines untouched
# ---------------------------------------------------------------------------

class RegressionPreservedTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        _seed_world()

    def test_gold_reference_topic_01_status_preserved(self):
        t1 = Lesson.objects.get(course__slug="onlenco-beginner", order=1)
        self.assertEqual(t1.status, "published")

    def test_topic_01_quality_score_high(self):
        t1 = Lesson.objects.get(course__slug="onlenco-beginner", order=1)
        result = content_quality_checker.check_lesson_quality(t1)
        self.assertGreaterEqual(result["score"], 90)

    def test_phase10_47_topics_all_pending_review(self):
        n = Lesson.objects.filter(
            course__slug="onlenco-beginner", status="pending_review",
        ).count()
        self.assertEqual(n, 47)
