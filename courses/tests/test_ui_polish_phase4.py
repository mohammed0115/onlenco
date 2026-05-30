"""Phase 4 — Game-like UI Polish — front-end markup tests.

Asserts the rendered HTML carries the expected polished hooks:
  * Challenge header components (progress / hearts / xp).
  * Feedback card variants (correct vs wrong) with aria-live.
  * Summary screen tiles + perfect badge + mistakes-review placeholder.
  * Lesson-detail launcher Start / Resume / Practice-again states.
  * Renderer fallbacks when metadata is missing (no 500, friendly text).
  * RTL helper text + LTR English question.
  * Regression — Challenge engine + Classic Quiz + Question Types Demo
    still work after the polish.
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import translation

from courses.models import (
    ChallengeAnswer, ChallengeSession, Course, CourseEnrollment,
    CourseLevel, CourseUnit, Lesson, LessonQuestion, LessonQuiz,
)


User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_course(slug="ui-poly"):
    level, _ = CourseLevel.objects.get_or_create(
        code="C0", defaults={"name": "UI tests", "order": 99},
    )
    teacher = User.objects.create_user(
        username=f"teacher-{slug}", password="pw",
        email=f"teacher-{slug}@onlenco.test",
    )
    course = Course.objects.create(
        title=f"UI {slug}", slug=slug, level=level,
        teacher=teacher, created_by=teacher,
        status="published", is_active=True,
    )
    unit = CourseUnit.objects.create(course=course, title="U1", order=1)
    lesson = Lesson.objects.create(
        course=course, unit=unit, title="Greetings", order=1,
        status="published", is_active=True,
    )
    quiz = LessonQuiz.objects.create(lesson=lesson, title="Q1")
    for i in range(4):
        LessonQuestion.objects.create(
            quiz=quiz, order=i + 1,
            question_type="multiple_choice",
            question_text=f"Pick the greeting #{i + 1}",
            options=["Hello", "Banana", "Window"],
            correct_answer="Hello",
        )
    return course, lesson, quiz


def _make_student(name="ui-student", *, lang="en"):
    u = User.objects.create_user(
        username=name, password="pw", email=f"{name}@onlenco.test",
    )
    if hasattr(u, "profile"):
        u.profile.email_verified = True
        u.profile.subscription_status = "active"
        # LanguagePreferenceMiddleware reads this on every request and
        # activates the profile's language — so without pinning it the
        # site renders Arabic regardless of cookies/headers.
        if hasattr(u.profile, "preferred_language"):
            u.profile.preferred_language = lang
        u.profile.save()
    return u


def _login(user, *, lang: str = "en"):
    """Login. Tests using English-text assertions wrap themselves in
    `translation.override('en')` so t_either picks the EN branch
    deterministically — the language() helper reads thread-local state,
    not the cookie."""
    c = Client(SERVER_NAME="127.0.0.1")
    c.force_login(user)
    c.cookies["django_language"] = lang
    return c


class _ForceEnglish:
    """Mixin: pin LANGUAGE_CODE to 'en' so LocaleMiddleware picks English
    when no other signal (cookie/header/url) is present. Applied via
    self._english_settings.{enable,disable}() because override_settings
    as a class decorator only works on SimpleTestCase subclasses.
    """
    @classmethod
    def setUpClass(cls):
        cls._english_settings = override_settings(LANGUAGE_CODE="en")
        cls._english_settings.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._english_settings.disable()


def _pin_session_to_question(student, lesson, quiz, question, *,
                             hearts_remaining=5):
    ChallengeSession.objects.filter(user=student, lesson=lesson).delete()
    return ChallengeSession.objects.create(
        user=student, lesson=lesson, quiz=quiz,
        status="in_progress", question_ids=[question.pk],
        total_questions=1, current_question_index=0,
        hearts_total=5, hearts_remaining=hearts_remaining,
    )


# ---------------------------------------------------------------------------
# 1. Challenge header markup
# ---------------------------------------------------------------------------

class ChallengeHeaderTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.course, cls.lesson, cls.quiz = _make_course("hdr")
        cls.student = _make_student("hdr-1")
        CourseEnrollment.objects.get_or_create(user=cls.student, course=cls.course)

    def setUp(self):
        self.client_ = _login(self.student)
        self.client_.get(
            reverse("courses:challenge_start", args=[self.course.pk, self.lesson.pk]),
            HTTP_HOST="127.0.0.1", follow=True,
        )
        self.session = ChallengeSession.objects.get(
            user=self.student, lesson=self.lesson,
        )

    def _current_body(self):
        r = self.client_.get(
            reverse("courses:challenge_current",
                    args=[self.course.pk, self.lesson.pk, self.session.pk]),
            HTTP_HOST="127.0.0.1",
        )
        self.assertEqual(r.status_code, 200)
        return r.content.decode("utf-8", errors="ignore")

    def test_challenge_page_uses_game_layout(self):
        body = self._current_body()
        self.assertIn("onlenco-ch-page", body)
        self.assertIn("onlenco-ch-card", body)
        self.assertIn("data-onlenco-challenge", body)

    def test_challenge_header_shows_progress_hearts_xp(self):
        body = self._current_body()
        self.assertIn("onlenco-ch-progress", body)
        self.assertIn("data-hearts", body)
        self.assertIn("data-xp", body)

    def test_progress_bar_visible(self):
        body = self._current_body()
        self.assertIn('role="progressbar"', body)
        self.assertIn("onlenco-ch-progress__fill", body)
        self.assertIn('aria-valuenow="1"', body)

    def test_hearts_visible(self):
        body = self._current_body()
        self.assertIn("onlenco-ch-heart", body)
        # All 5 hearts rendered, none lost on a fresh session.
        # Each heart is a `<span ...>♥</span>`; count the glyph.
        self.assertEqual(body.count("♥"), 5)

    def test_xp_badge_visible(self):
        body = self._current_body()
        self.assertIn("onlenco-ch-xp__bolt", body)
        self.assertIn("onlenco-ch-xp__value", body)

    def test_exit_button_has_aria_label(self):
        body = self._current_body()
        self.assertIn("onlenco-ch-exit", body)
        self.assertIn("aria-label", body)


# ---------------------------------------------------------------------------
# 2. Feedback card (correct vs wrong)
# ---------------------------------------------------------------------------

class FeedbackCardTests(_ForceEnglish, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.course, cls.lesson, cls.quiz = _make_course("fbk")
        cls.student = _make_student("fbk-1")
        CourseEnrollment.objects.get_or_create(user=cls.student, course=cls.course)
        cls.question = cls.quiz.questions.first()

    def _answer_and_show(self, *, correct: bool):
        session = _pin_session_to_question(
            self.student, self.lesson, self.quiz, self.question,
        )
        ChallengeAnswer.objects.create(
            session=session, question=self.question,
            user_answer="Hello" if correct else "Banana",
            is_correct=correct,
            score=1.0 if correct else 0.0,
            xp_awarded=10 if correct else 0,
            heart_lost=False if correct else True,
            feedback_en="Sample feedback.",
        )
        if not correct:
            session.wrong_count = 1
            session.hearts_remaining = 4
            session.save()
        else:
            session.correct_count = 1
            session.xp_earned = 10
            session.save()
        c = _login(self.student)
        r = c.get(reverse("courses:challenge_current",
                          args=[self.course.pk, self.lesson.pk, session.pk]),
                  HTTP_HOST="127.0.0.1")
        self.assertEqual(r.status_code, 200)
        return r.content.decode("utf-8", errors="ignore")

    def test_feedback_card_correct_visible(self):
        body = self._answer_and_show(correct=True)
        self.assertIn("onlenco-ch-card--correct", body)
        self.assertIn("data-feedback-card", body)
        self.assertIn("XP", body)
        self.assertIn('role="status"', body)
        self.assertIn('aria-live="polite"', body)

    def test_feedback_card_wrong_visible(self):
        body = self._answer_and_show(correct=False)
        self.assertIn("onlenco-ch-card--wrong", body)
        # Encouraging microcopy — not "Wrong." / "Incorrect."
        self.assertIn("Good try", body)
        # Correct answer is shown.
        self.assertIn("Hello", body)


# ---------------------------------------------------------------------------
# 3. Summary screen
# ---------------------------------------------------------------------------

class SummaryScreenTests(_ForceEnglish, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.course, cls.lesson, cls.quiz = _make_course("sum")
        cls.student = _make_student("sum-1")
        CourseEnrollment.objects.get_or_create(user=cls.student, course=cls.course)

    def _summary(self, *, status, correct, wrong, hearts_remaining=5, xp=0):
        ChallengeSession.objects.filter(user=self.student, lesson=self.lesson).delete()
        from django.utils import timezone
        session = ChallengeSession.objects.create(
            user=self.student, lesson=self.lesson, quiz=self.quiz,
            status=status, question_ids=[1], total_questions=correct + wrong,
            current_question_index=0,
            hearts_total=5, hearts_remaining=hearts_remaining,
            xp_earned=xp, correct_count=correct, wrong_count=wrong,
            completed_at=timezone.now(),
        )
        c = _login(self.student)
        r = c.get(reverse("courses:challenge_summary",
                          args=[self.course.pk, self.lesson.pk, session.pk]),
                  HTTP_HOST="127.0.0.1")
        self.assertEqual(r.status_code, 200)
        return r.content.decode("utf-8", errors="ignore")

    def test_summary_screen_shows_xp_accuracy_hearts(self):
        body = self._summary(status="completed", correct=4, wrong=0, xp=40)
        self.assertIn("onlenco-ch-summary", body)
        self.assertIn("onlenco-ch-summary__tile", body)
        # XP tile
        self.assertIn("40", body)
        # Accuracy 100%
        self.assertIn("100%", body)
        # Hearts left
        self.assertIn("5 / 5", body)

    def test_summary_perfect_run_shows_perfect_badge(self):
        body = self._summary(status="completed", correct=5, wrong=0, xp=60)
        self.assertIn("onlenco-ch-summary__perfect-pill", body)
        self.assertIn("Perfect", body)
        self.assertIn('data-perfect="1"', body)

    def test_summary_failed_state_shows_practice_again(self):
        body = self._summary(status="failed", correct=2, wrong=5,
                             hearts_remaining=0, xp=20)
        self.assertIn("Practice again", body)
        self.assertIn('data-action="practice-again"', body)
        # Encouraging — not punitive
        self.assertIn("Good effort", body)

    def test_summary_shows_mistakes_review_placeholder_when_wrong(self):
        body = self._summary(status="completed", correct=3, wrong=1, xp=30)
        self.assertIn('data-action="review-mistakes"', body)
        self.assertIn('data-placeholder="1"', body)
        self.assertIn("Review mistakes", body)

    def test_summary_no_mistakes_review_when_perfect(self):
        body = self._summary(status="completed", correct=5, wrong=0, xp=60)
        self.assertNotIn('data-action="review-mistakes"', body)


# ---------------------------------------------------------------------------
# 4. Lesson detail launcher states
# ---------------------------------------------------------------------------

class LessonDetailLauncherTests(_ForceEnglish, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.course, cls.lesson, cls.quiz = _make_course("launch")
        cls.student = _make_student("launch-1")
        CourseEnrollment.objects.get_or_create(user=cls.student, course=cls.course)

    def _lesson_body(self):
        c = _login(self.student)
        r = c.get(reverse("courses:lesson_detail",
                          args=[self.course.pk, self.lesson.pk]),
                  HTTP_HOST="127.0.0.1")
        self.assertEqual(r.status_code, 200)
        return r.content.decode("utf-8", errors="ignore")

    def test_lesson_detail_shows_start_challenge(self):
        body = self._lesson_body()
        self.assertIn('data-action="start-challenge"', body)
        self.assertIn("Start Game Challenge", body)

    def test_lesson_detail_shows_classic_quiz(self):
        body = self._lesson_body()
        self.assertIn('data-action="classic-quiz"', body)
        self.assertIn("Classic Quiz", body)

    def test_resume_challenge_button_visible_for_active_session(self):
        ChallengeSession.objects.create(
            user=self.student, lesson=self.lesson, quiz=self.quiz,
            status="in_progress", question_ids=[1, 2, 3], total_questions=3,
            current_question_index=1,
            hearts_total=5, hearts_remaining=4,
        )
        body = self._lesson_body()
        self.assertIn('data-action="resume-challenge"', body)
        self.assertIn("Resume Challenge", body)
        self.assertNotIn('data-action="start-challenge"', body)

    def test_practice_again_visible_after_completion(self):
        ChallengeSession.objects.create(
            user=self.student, lesson=self.lesson, quiz=self.quiz,
            status="completed", question_ids=[1, 2, 3], total_questions=3,
            current_question_index=3,
            hearts_total=5, hearts_remaining=3,
            correct_count=3, wrong_count=0,
        )
        body = self._lesson_body()
        self.assertIn('data-action="practice-challenge"', body)
        self.assertIn("Practice Again", body)


# ---------------------------------------------------------------------------
# 5. Renderer fallbacks (missing metadata never 500s)
# ---------------------------------------------------------------------------

class RendererFallbackTests(_ForceEnglish, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.course, cls.lesson, cls.quiz = _make_course("fb")
        # Wipe the default MCQs — we want to add fallback cases ourselves.
        cls.quiz.questions.all().delete()
        cls.student = _make_student("fb-1")
        CourseEnrollment.objects.get_or_create(user=cls.student, course=cls.course)

    def _add(self, **kw):
        return LessonQuestion.objects.create(
            quiz=self.quiz, order=99,
            question_text="Fallback test",
            **kw,
        )

    def _render(self, question):
        session = _pin_session_to_question(
            self.student, self.lesson, self.quiz, question,
        )
        c = _login(self.student)
        r = c.get(reverse("courses:challenge_current",
                          args=[self.course.pk, self.lesson.pk, session.pk]),
                  HTTP_HOST="127.0.0.1")
        return r

    def test_image_choice_without_image_uses_placeholder(self):
        q = self._add(
            question_type="image_choice",
            metadata={"options": [
                {"id": "a", "text": "Window", "image_url": ""},
                {"id": "b", "text": "Door",   "image_url": ""},
            ], "correct_option_id": "a"},
        )
        r = self._render(q)
        self.assertEqual(r.status_code, 200)
        self.assertIn("onlenco-qr__image-placeholder", r.content.decode())

    def test_listen_and_choose_without_audio_uses_placeholder(self):
        q = self._add(
            question_type="listen_and_choose",
            metadata={"audio_script": "Hi there.",
                      "options": [{"id": "a", "text": "Hi"}],
                      "correct_option_id": "a"},
        )
        r = self._render(q)
        self.assertEqual(r.status_code, 200)
        body = r.content.decode()
        self.assertIn("Audio coming soon", body)
        # The transcript is shown in the placeholder so the student can still play.
        self.assertIn("Hi there.", body)

    def test_picture_labeling_without_image_uses_placeholder(self):
        q = self._add(
            question_type="picture_labeling",
            metadata={"image_prompt": "A small clay cup of tea.",
                      "image_url": "",
                      "accepted_answers": ["tea"]},
            correct_answer="tea",
        )
        r = self._render(q)
        self.assertEqual(r.status_code, 200)
        body = r.content.decode()
        self.assertIn("Image coming soon", body)
        self.assertIn("A small clay cup of tea.", body)

    def test_listen_and_choose_without_options_uses_empty_state(self):
        q = self._add(
            question_type="listen_and_choose",
            metadata={"audio_script": "Hi", "options": [],
                      "correct_option_id": ""},
        )
        r = self._render(q)
        self.assertEqual(r.status_code, 200)
        self.assertIn("onlenco-qr--empty", r.content.decode())

    def test_missing_metadata_does_not_500(self):
        q = self._add(
            question_type="tap_choice",
            metadata={},   # completely empty
        )
        r = self._render(q)
        self.assertEqual(r.status_code, 200)


# ---------------------------------------------------------------------------
# 6. Renderer visual hooks (game-card style + per-type expectations)
# ---------------------------------------------------------------------------

class RendererVisualHookTests(_ForceEnglish, TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_course_levels", verbosity=0)
        call_command("seed_challenge_question_types_demo", verbosity=0)
        cls.lesson = Lesson.objects.get(title="Challenge Types Showcase")
        cls.course = cls.lesson.course
        cls.student = _make_student("vis-1")
        CourseEnrollment.objects.get_or_create(user=cls.student, course=cls.course)

    def _render_q(self, question_type):
        q = self.lesson.quiz.questions.get(question_type=question_type)
        session = _pin_session_to_question(
            self.student, self.lesson, self.lesson.quiz, q,
        )
        c = _login(self.student)
        return c.get(reverse("courses:challenge_current",
                             args=[self.course.pk, self.lesson.pk, session.pk]),
                     HTTP_HOST="127.0.0.1").content.decode()

    def test_all_question_renderers_have_game_card_style(self):
        for q in self.lesson.quiz.questions.all().order_by("order"):
            with self.subTest(qt=q.question_type):
                body = self._render_q(q.question_type)
                self.assertIn("onlenco-ch-card", body)
                self.assertIn("onlenco-qr", body)

    def test_word_bank_mobile_friendly_markup(self):
        body = self._render_q("word_bank_sentence")
        self.assertIn("data-word-bank", body)
        self.assertIn("data-word-bank-reset", body)

    def test_match_pairs_mobile_friendly_markup(self):
        body = self._render_q("match_pairs")
        self.assertIn("data-match-root", body)
        self.assertIn("onlenco-qr__match-col", body)

    def test_frequency_scale_visible(self):
        body = self._render_q("frequency_scale")
        self.assertIn("onlenco-qr__scale-range", body)
        self.assertIn("data-scale-range", body)

    def test_conversation_reply_uses_chat_bubbles(self):
        body = self._render_q("conversation_reply")
        self.assertIn("onlenco-qr__bubble", body)
        self.assertIn("onlenco-qr__chat", body)

    def test_speaking_placeholder_clear(self):
        body = self._render_q("speak_this_sentence")
        # The "coming soon" pill must show — the student should never
        # think AI is grading their voice right now.
        self.assertIn("AI speaking feedback coming soon", body)


# ---------------------------------------------------------------------------
# 7. RTL / LTR
# ---------------------------------------------------------------------------

class DirectionalityTests(_ForceEnglish, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.course, cls.lesson, cls.quiz = _make_course("dir")
        cls.quiz.questions.all().delete()
        # Avoid apostrophe — Django escapes it to &#x27; in HTML.
        cls.q = LessonQuestion.objects.create(
            quiz=cls.quiz, order=1, question_type="tap_choice",
            question_text="What does Noor do at the clinic?",
            question_text_ar="ماذا تفعل نور في العيادة؟",
            metadata={"options": [{"id": "a", "text": "nurse"}],
                      "correct_option_id": "a"},
            correct_answer="a",
        )
        cls.student_en = _make_student("dir-en", lang="en")
        cls.student_ar = _make_student("dir-ar", lang="ar")
        CourseEnrollment.objects.get_or_create(user=cls.student_en, course=cls.course)
        CourseEnrollment.objects.get_or_create(user=cls.student_ar, course=cls.course)

    def _body(self, student):
        session = _pin_session_to_question(
            student, self.lesson, self.quiz, self.q,
        )
        c = _login(student)
        r = c.get(reverse("courses:challenge_current",
                          args=[self.course.pk, self.lesson.pk, session.pk]),
                  HTTP_HOST="127.0.0.1")
        return r.content.decode()

    def test_english_question_renders_ltr(self):
        body = self._body(self.student_en)
        self.assertIn('dir="ltr"', body)
        self.assertIn("What does Noor do at the clinic?", body)

    def test_arabic_helper_renders_rtl(self):
        body = self._body(self.student_ar)
        # The Arabic helper paragraph carries dir="rtl"
        self.assertIn('dir="rtl"', body)
        # And the Arabic helper text is rendered when profile lang is ar.
        self.assertIn("ماذا تفعل نور في العيادة؟", body)


# ---------------------------------------------------------------------------
# 8. Regression — engine still works end-to-end
# ---------------------------------------------------------------------------

class RegressionAfterPolishTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.course, cls.lesson, cls.quiz = _make_course("reg")
        cls.student = _make_student("reg-1")
        CourseEnrollment.objects.get_or_create(user=cls.student, course=cls.course)

    def test_challenge_flow_still_works_after_ui_polish(self):
        c = _login(self.student)
        r = c.get(reverse("courses:challenge_start",
                          args=[self.course.pk, self.lesson.pk]),
                  HTTP_HOST="127.0.0.1", follow=True)
        self.assertEqual(r.status_code, 200)
        session = ChallengeSession.objects.get(
            user=self.student, lesson=self.lesson,
        )
        # Submit one correct answer.
        first_qid = session.question_ids[0]
        c.post(reverse("courses:challenge_answer",
                       args=[self.course.pk, self.lesson.pk, session.pk]),
               {"question_id": first_qid, "answer": "Hello"},
               HTTP_HOST="127.0.0.1")
        session.refresh_from_db()
        self.assertEqual(session.correct_count, 1)
        self.assertGreater(session.xp_earned, 0)

    def test_legacy_quiz_still_works(self):
        c = _login(self.student)
        r = c.get(reverse("courses:lesson_quiz_attempt",
                          args=[self.course.pk, self.lesson.pk]),
                  HTTP_HOST="127.0.0.1")
        self.assertEqual(r.status_code, 200)

    def test_challenge_page_no_500_error(self):
        c = _login(self.student)
        c.get(reverse("courses:challenge_start",
                      args=[self.course.pk, self.lesson.pk]),
              HTTP_HOST="127.0.0.1", follow=True)
        session = ChallengeSession.objects.get(
            user=self.student, lesson=self.lesson,
        )
        for route in ("courses:challenge_current",
                      "courses:challenge_summary"):
            r = c.get(reverse(route,
                              args=[self.course.pk, self.lesson.pk, session.pk]),
                      HTTP_HOST="127.0.0.1")
            self.assertNotEqual(r.status_code, 500,
                                f"{route} returned 500")


class DemoSeedStillWorksTests(TestCase):
    def test_question_types_demo_still_runs(self):
        call_command("seed_course_levels", verbosity=0)
        call_command("seed_challenge_question_types_demo", verbosity=0)
        lesson = Lesson.objects.get(title="Challenge Types Showcase")
        self.assertEqual(lesson.quiz.questions.count(), 20)
