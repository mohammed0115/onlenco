"""Phase 1 Game Challenge Engine — server-side tests.

Covers the 13 acceptance criteria from Prompt 02 plus a few extras
(ownership, idempotency, legacy compatibility).
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from courses.models import (
    ChallengeAnswer, ChallengeSession, Course, CourseEnrollment,
    CourseLevel, CourseUnit, Lesson, LessonQuestion, LessonQuiz,
)


User = get_user_model()


def _make_lesson_with_quiz(
    *, slug: str = "ch-course", title: str = "Challenge Course",
    n_mcq: int = 4, n_fill: int = 2,
) -> tuple[Course, Lesson, LessonQuiz]:
    level, _ = CourseLevel.objects.get_or_create(
        code="C0", defaults={"name": "Challenge tests", "order": 99},
    )
    teacher = User.objects.create_user(
        username=f"teacher-{slug}", password="pw",
        email=f"teacher-{slug}@onlenco.test",
    )
    course = Course.objects.create(
        title=title, slug=slug, level=level,
        teacher=teacher, created_by=teacher,
        status="published", is_active=True,
    )
    unit = CourseUnit.objects.create(course=course, title="U1", order=1)
    lesson = Lesson.objects.create(
        course=course, unit=unit, title="L1", order=1,
        status="published", is_active=True,
    )
    quiz = LessonQuiz.objects.create(lesson=lesson, title="Q1")

    for i in range(n_mcq):
        LessonQuestion.objects.create(
            quiz=quiz, order=i + 1,
            question_type="multiple_choice",
            question_text=f"Pick the greeting #{i + 1}",
            options=["Hello", "Banana", "Window"],
            correct_answer="Hello",
        )
    for j in range(n_fill):
        LessonQuestion.objects.create(
            quiz=quiz, order=n_mcq + j + 1,
            question_type="fill_blank",
            question_text=f"My name ___ Amani #{j + 1}",
            options=[],
            correct_answer="is",
        )
    return course, lesson, quiz


def _make_student(name: str = "alice") -> User:
    u = User.objects.create_user(
        username=name, password="pw", email=f"{name}@onlenco.test",
    )
    if hasattr(u, "profile"):
        u.profile.email_verified = True
        u.profile.subscription_status = "active"
        u.profile.save()
    return u


def _login(user) -> Client:
    c = Client(SERVER_NAME="127.0.0.1")
    c.force_login(user)
    return c


# ---------------------------------------------------------------------
# 1–2. Session lifecycle (start + resume)
# ---------------------------------------------------------------------

class SessionLifecycleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.course, cls.lesson, cls.quiz = _make_lesson_with_quiz()
        cls.student = _make_student("life-1")
        CourseEnrollment.objects.get_or_create(user=cls.student, course=cls.course)

    def test_challenge_session_starts(self):
        c = _login(self.student)
        r = c.get(reverse(
            "courses:challenge_start",
            args=[self.course.pk, self.lesson.pk],
        ), HTTP_HOST="127.0.0.1", follow=True)
        self.assertEqual(r.status_code, 200)
        sess = ChallengeSession.objects.get(
            user=self.student, lesson=self.lesson,
        )
        self.assertEqual(sess.status, "in_progress")
        self.assertEqual(sess.current_question_index, 0)
        self.assertEqual(sess.hearts_remaining, 5)
        self.assertEqual(sess.xp_earned, 0)
        self.assertEqual(sess.total_questions, 6)  # 4 MCQ + 2 fill

    def test_challenge_session_resumes_if_existing(self):
        c = _login(self.student)
        # Start once
        c.get(reverse("courses:challenge_start",
                      args=[self.course.pk, self.lesson.pk]),
              HTTP_HOST="127.0.0.1", follow=True)
        first = ChallengeSession.objects.get(user=self.student, lesson=self.lesson)
        # Start again
        c.get(reverse("courses:challenge_start",
                      args=[self.course.pk, self.lesson.pk]),
              HTTP_HOST="127.0.0.1", follow=True)
        again = ChallengeSession.objects.get(user=self.student, lesson=self.lesson)
        # Same row — resume, no fork
        self.assertEqual(first.pk, again.pk)
        # And there is exactly ONE active session per (user, lesson).
        active = ChallengeSession.objects.filter(
            user=self.student, lesson=self.lesson,
            status__in=("started", "in_progress"),
        )
        self.assertEqual(active.count(), 1)


# ---------------------------------------------------------------------
# 3–4. One card at a time + correct indexing
# ---------------------------------------------------------------------

class OneCardAtATimeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.course, cls.lesson, cls.quiz = _make_lesson_with_quiz()
        cls.student = _make_student("oc-1")
        CourseEnrollment.objects.get_or_create(user=cls.student, course=cls.course)

    def _start(self, c):
        c.get(reverse("courses:challenge_start",
                      args=[self.course.pk, self.lesson.pk]),
              HTTP_HOST="127.0.0.1", follow=True)
        return ChallengeSession.objects.get(user=self.student, lesson=self.lesson)

    def test_challenge_shows_one_question_at_a_time(self):
        c = _login(self.student)
        session = self._start(c)
        r = c.get(reverse("courses:challenge_current",
                           args=[self.course.pk, self.lesson.pk, session.pk]),
                   HTTP_HOST="127.0.0.1")
        self.assertEqual(r.status_code, 200)
        body = r.content.decode("utf-8", errors="ignore")
        # Exactly one question text rendered.
        self.assertEqual(body.count('class="onlenco-ch-question__text"'), 1)
        # And the answer form for this question.
        first_qid = session.question_ids[0]
        self.assertIn(f'value="{first_qid}"', body)

    def test_current_question_matches_session_index(self):
        c = _login(self.student)
        session = self._start(c)
        # Answer the first card correctly then continue.
        first_q = LessonQuestion.objects.get(pk=session.question_ids[0])
        c.post(reverse("courses:challenge_answer",
                       args=[self.course.pk, self.lesson.pk, session.pk]),
               {"question_id": first_q.pk, "answer": "Hello"},
               HTTP_HOST="127.0.0.1")
        c.post(reverse("courses:challenge_continue",
                       args=[self.course.pk, self.lesson.pk, session.pk]),
               HTTP_HOST="127.0.0.1")
        session.refresh_from_db()
        self.assertEqual(session.current_question_index, 1)
        # The page now shows the second question's id, not the first.
        r = c.get(reverse("courses:challenge_current",
                           args=[self.course.pk, self.lesson.pk, session.pk]),
                   HTTP_HOST="127.0.0.1")
        body = r.content.decode("utf-8", errors="ignore")
        self.assertIn(f'value="{session.question_ids[1]}"', body)


# ---------------------------------------------------------------------
# 5–7. Answer flow: persistence, XP, hearts
# ---------------------------------------------------------------------

class AnswerFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.course, cls.lesson, cls.quiz = _make_lesson_with_quiz()
        cls.student = _make_student("ans-1")
        CourseEnrollment.objects.get_or_create(user=cls.student, course=cls.course)

    def _bootstrap(self) -> tuple[Client, ChallengeSession]:
        c = _login(self.student)
        c.get(reverse("courses:challenge_start",
                       args=[self.course.pk, self.lesson.pk]),
              HTTP_HOST="127.0.0.1", follow=True)
        sess = ChallengeSession.objects.get(user=self.student, lesson=self.lesson)
        return c, sess

    def test_submit_correct_answer_saves_answer(self):
        c, session = self._bootstrap()
        q = LessonQuestion.objects.get(pk=session.question_ids[0])
        c.post(reverse("courses:challenge_answer",
                       args=[self.course.pk, self.lesson.pk, session.pk]),
               {"question_id": q.pk, "answer": "Hello"},
               HTTP_HOST="127.0.0.1")
        row = ChallengeAnswer.objects.get(session=session, question=q)
        self.assertTrue(row.is_correct)
        self.assertEqual(row.user_answer, "Hello")

    def test_correct_answer_adds_xp(self):
        c, session = self._bootstrap()
        q = LessonQuestion.objects.get(pk=session.question_ids[0])
        c.post(reverse("courses:challenge_answer",
                       args=[self.course.pk, self.lesson.pk, session.pk]),
               {"question_id": q.pk, "answer": "Hello"},
               HTTP_HOST="127.0.0.1")
        session.refresh_from_db()
        self.assertEqual(session.xp_earned, 10)
        self.assertEqual(session.correct_count, 1)

    def test_wrong_answer_removes_heart(self):
        c, session = self._bootstrap()
        q = LessonQuestion.objects.get(pk=session.question_ids[0])
        c.post(reverse("courses:challenge_answer",
                       args=[self.course.pk, self.lesson.pk, session.pk]),
               {"question_id": q.pk, "answer": "Banana"},
               HTTP_HOST="127.0.0.1")
        session.refresh_from_db()
        self.assertEqual(session.hearts_remaining, 4)
        self.assertEqual(session.wrong_count, 1)
        self.assertEqual(session.xp_earned, 0)

    def test_wrong_answer_saves_feedback(self):
        c, session = self._bootstrap()
        q = LessonQuestion.objects.get(pk=session.question_ids[0])
        c.post(reverse("courses:challenge_answer",
                       args=[self.course.pk, self.lesson.pk, session.pk]),
               {"question_id": q.pk, "answer": "Banana"},
               HTTP_HOST="127.0.0.1")
        row = ChallengeAnswer.objects.get(session=session, question=q)
        self.assertFalse(row.is_correct)
        self.assertTrue(row.heart_lost)
        # Feedback strings exist (en at minimum).
        self.assertTrue(row.feedback_en or row.feedback_ar
                        or "Expected" in (row.feedback_en or ""))


# ---------------------------------------------------------------------
# 8–11. Continue + completion + summary + refresh + ownership
# ---------------------------------------------------------------------

class CompletionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.course, cls.lesson, cls.quiz = _make_lesson_with_quiz(n_mcq=2, n_fill=0)
        cls.student = _make_student("done-1")
        CourseEnrollment.objects.get_or_create(user=cls.student, course=cls.course)

    def _play_through(self, answers):
        """Walk the whole session submitting the given answers in order."""
        c = _login(self.student)
        c.get(reverse("courses:challenge_start",
                       args=[self.course.pk, self.lesson.pk]),
              HTTP_HOST="127.0.0.1", follow=True)
        session = ChallengeSession.objects.get(user=self.student, lesson=self.lesson)
        for i, ans in enumerate(answers):
            q = LessonQuestion.objects.get(pk=session.question_ids[i])
            c.post(reverse("courses:challenge_answer",
                           args=[self.course.pk, self.lesson.pk, session.pk]),
                   {"question_id": q.pk, "answer": ans},
                   HTTP_HOST="127.0.0.1")
            c.post(reverse("courses:challenge_continue",
                           args=[self.course.pk, self.lesson.pk, session.pk]),
                   HTTP_HOST="127.0.0.1")
        session.refresh_from_db()
        return c, session

    def test_continue_moves_to_next_question(self):
        c = _login(self.student)
        c.get(reverse("courses:challenge_start",
                       args=[self.course.pk, self.lesson.pk]),
              HTTP_HOST="127.0.0.1", follow=True)
        session = ChallengeSession.objects.get(user=self.student, lesson=self.lesson)
        q = LessonQuestion.objects.get(pk=session.question_ids[0])
        c.post(reverse("courses:challenge_answer",
                       args=[self.course.pk, self.lesson.pk, session.pk]),
               {"question_id": q.pk, "answer": "Hello"},
               HTTP_HOST="127.0.0.1")
        c.post(reverse("courses:challenge_continue",
                       args=[self.course.pk, self.lesson.pk, session.pk]),
               HTTP_HOST="127.0.0.1")
        session.refresh_from_db()
        self.assertEqual(session.current_question_index, 1)

    def test_challenge_completes_after_last_question(self):
        c, session = self._play_through(["Hello", "Hello"])
        self.assertEqual(session.status, "completed")
        # XP: 10 + 10 + 20 (completion bonus) + 10 (perfect bonus) = 50
        self.assertEqual(session.xp_earned, 50)
        self.assertEqual(session.correct_count, 2)
        self.assertEqual(session.wrong_count, 0)
        self.assertIsNotNone(session.completed_at)

    def test_summary_shows_xp_accuracy_and_hearts(self):
        c, session = self._play_through(["Hello", "Hello"])
        r = c.get(reverse("courses:challenge_summary",
                           args=[self.course.pk, self.lesson.pk, session.pk]),
                   HTTP_HOST="127.0.0.1")
        self.assertEqual(r.status_code, 200)
        body = r.content.decode("utf-8", errors="ignore")
        self.assertIn(str(session.xp_earned), body)
        self.assertIn(f"{session.accuracy_pct}%", body)
        self.assertIn(f"{session.hearts_remaining} / {session.hearts_total}", body)

    def test_refresh_does_not_reset_session(self):
        c = _login(self.student)
        c.get(reverse("courses:challenge_start",
                       args=[self.course.pk, self.lesson.pk]),
              HTTP_HOST="127.0.0.1", follow=True)
        session = ChallengeSession.objects.get(user=self.student, lesson=self.lesson)
        first_id = session.pk
        # Re-visit start
        c.get(reverse("courses:challenge_start",
                       args=[self.course.pk, self.lesson.pk]),
              HTTP_HOST="127.0.0.1", follow=True)
        session.refresh_from_db()
        self.assertEqual(session.pk, first_id)
        self.assertEqual(session.current_question_index, 0)
        # GETting /current/ again is idempotent — no state change.
        c.get(reverse("courses:challenge_current",
                       args=[self.course.pk, self.lesson.pk, session.pk]),
              HTTP_HOST="127.0.0.1")
        session.refresh_from_db()
        self.assertEqual(session.current_question_index, 0)

    def test_user_cannot_access_other_user_session(self):
        # Set up own session
        c = _login(self.student)
        c.get(reverse("courses:challenge_start",
                       args=[self.course.pk, self.lesson.pk]),
              HTTP_HOST="127.0.0.1", follow=True)
        my_session = ChallengeSession.objects.get(user=self.student, lesson=self.lesson)
        # Another student tries to open it
        other = _make_student("done-2")
        CourseEnrollment.objects.get_or_create(user=other, course=self.course)
        c2 = _login(other)
        r = c2.get(reverse("courses:challenge_current",
                            args=[self.course.pk, self.lesson.pk, my_session.pk]),
                    HTTP_HOST="127.0.0.1")
        self.assertEqual(r.status_code, 404)


# ---------------------------------------------------------------------
# 12–14. Anti-cheat / idempotency
# ---------------------------------------------------------------------

class GuardrailTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.course, cls.lesson, cls.quiz = _make_lesson_with_quiz(n_mcq=2, n_fill=0)
        cls.student = _make_student("guard-1")
        CourseEnrollment.objects.get_or_create(user=cls.student, course=cls.course)

    def _bootstrap(self):
        c = _login(self.student)
        c.get(reverse("courses:challenge_start",
                       args=[self.course.pk, self.lesson.pk]),
              HTTP_HOST="127.0.0.1", follow=True)
        sess = ChallengeSession.objects.get(user=self.student, lesson=self.lesson)
        return c, sess

    def test_user_cannot_answer_non_current_question(self):
        c, session = self._bootstrap()
        # Try to answer the SECOND question while parked on the first.
        future_q = LessonQuestion.objects.get(pk=session.question_ids[1])
        c.post(reverse("courses:challenge_answer",
                       args=[self.course.pk, self.lesson.pk, session.pk]),
               {"question_id": future_q.pk, "answer": "Hello"},
               HTTP_HOST="127.0.0.1")
        # No ChallengeAnswer created.
        self.assertFalse(
            ChallengeAnswer.objects.filter(session=session).exists()
        )

    def test_duplicate_answer_is_prevented(self):
        c, session = self._bootstrap()
        q = LessonQuestion.objects.get(pk=session.question_ids[0])
        c.post(reverse("courses:challenge_answer",
                       args=[self.course.pk, self.lesson.pk, session.pk]),
               {"question_id": q.pk, "answer": "Hello"},
               HTTP_HOST="127.0.0.1")
        # Second submission for the same card — no second row.
        c.post(reverse("courses:challenge_answer",
                       args=[self.course.pk, self.lesson.pk, session.pk]),
               {"question_id": q.pk, "answer": "Banana"},
               HTTP_HOST="127.0.0.1")
        self.assertEqual(
            ChallengeAnswer.objects.filter(session=session, question=q).count(), 1,
        )
        session.refresh_from_db()
        # XP is awarded once.
        self.assertEqual(session.xp_earned, 10)


# ---------------------------------------------------------------------
# 15. Legacy compatibility
# ---------------------------------------------------------------------

class LegacyQuizCompatibilityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.course, cls.lesson, cls.quiz = _make_lesson_with_quiz(
            slug="legacy-course", n_mcq=2, n_fill=0,
        )
        cls.student = _make_student("legacy-1")
        CourseEnrollment.objects.get_or_create(user=cls.student, course=cls.course)

    def test_legacy_quiz_still_works(self):
        c = _login(self.student)
        # GET the legacy quiz page
        r = c.get(reverse("courses:lesson_quiz_attempt",
                           args=[self.course.pk, self.lesson.pk]),
                   HTTP_HOST="127.0.0.1")
        self.assertNotEqual(r.status_code, 500)
        # POST with at least one answer
        r = c.post(reverse("courses:lesson_quiz_attempt",
                            args=[self.course.pk, self.lesson.pk]),
                    {f"q_{q.id}": "Hello" for q in self.quiz.questions.all()},
                    HTTP_HOST="127.0.0.1")
        self.assertNotEqual(r.status_code, 500)


# ---------------------------------------------------------------------
# 16–17. Robustness
# ---------------------------------------------------------------------

class RobustnessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.course, cls.lesson, cls.quiz = _make_lesson_with_quiz(n_mcq=1, n_fill=0)
        cls.student = _make_student("rob-1")
        CourseEnrollment.objects.get_or_create(user=cls.student, course=cls.course)

    def test_unsupported_question_type_does_not_500(self):
        # Add a question of a type the composer drops. In Phase 3 the
        # composer pulls its support list from the registry — speaking
        # types are now placeholders that DO enter the deck, so we test
        # with `writing_prompt` instead (supports_challenge=False, open-
        # ended, lives in Classic Quiz only).
        LessonQuestion.objects.create(
            quiz=self.quiz, order=99,
            question_type="writing_prompt",
            question_text="Write a paragraph about your morning.",
            options=[],
            correct_answer="(model)",
        )
        c = _login(self.student)
        r = c.get(reverse("courses:challenge_start",
                           args=[self.course.pk, self.lesson.pk]),
                   HTTP_HOST="127.0.0.1", follow=True)
        self.assertNotEqual(r.status_code, 500)
        session = ChallengeSession.objects.get(user=self.student, lesson=self.lesson)
        # The unsupported question is NOT in the sequence.
        self.assertEqual(session.total_questions, 1)

    def test_challenge_page_no_500_error(self):
        c = _login(self.student)
        c.get(reverse("courses:challenge_start",
                       args=[self.course.pk, self.lesson.pk]),
              HTTP_HOST="127.0.0.1", follow=True)
        session = ChallengeSession.objects.get(user=self.student, lesson=self.lesson)
        for route in ("courses:challenge_current",
                      "courses:challenge_summary"):
            r = c.get(reverse(route, args=[self.course.pk, self.lesson.pk, session.pk]),
                       HTTP_HOST="127.0.0.1")
            self.assertNotEqual(r.status_code, 500,
                                f"{route} returned 500")
