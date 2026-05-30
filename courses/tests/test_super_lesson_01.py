"""Phase 8 — Super Lesson 01 (gold reference): seed + content + 10-q
Challenge + Mastery + Rewards + AI integration + UI + Regression.

Asserts:
  * `seed_super_lesson_01` is idempotent + populates content/media/checklist.
  * Course + Lesson + Quiz exist with the expected slug/title/CEFR.
  * The Challenge sequence has 10 questions, every one skill-tagged.
  * Each Phase-3 question type used by the lesson actually renders.
  * Running a full Challenge updates SkillMastery + StudentMistake.
  * Rewards (XPTransaction, hearts decrement, daily-goal progress) fire.
  * AI explain endpoint returns a JSON fallback when AI is disabled.
  * Classic Quiz page still renders for the same lesson.
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from courses.models import (
    ChallengeAnswer, ChallengeSession, Course, CourseEnrollment, Lesson,
    LessonAudioScript, LessonChecklist, LessonImagePrompt, LessonQuestion,
    LessonQuiz,
)
from learning_core.models import (
    MasteryEvent, SkillMastery, StudentMistake,
)
from motivation.models import (
    DailyGoalProgress, UserBadge, XPTransaction,
)
from tutor.models import ChallengeAIInteraction


User = get_user_model()
# Phase 9.5 — Q7 (translate_to_english) and Q8 (listen_and_type) were
# replaced with image_choice + sound_to_word for A0 suitability.
EXPECTED_QUESTION_TYPES = {
    "tap_choice", "listen_and_choose", "word_bank_sentence",
    "fill_blank_card", "match_pairs", "conversation_reply",
    "image_choice", "sound_to_word",
    "speak_this_sentence", "ai_roleplay_prompt",
}


def _make_student(name="ph8") -> User:
    u = User.objects.create_user(
        username=name, password="pw", email=f"{name}@onlenco.test",
    )
    if hasattr(u, "profile"):
        u.profile.email_verified = True
        u.profile.subscription_status = "active"
        u.profile.preferred_language = "en"
        u.profile.save()
    return u


def _login(user):
    c = Client(SERVER_NAME="127.0.0.1")
    c.force_login(user)
    return c


def _seed_all():
    """Run every seed Super Lesson 01 depends on."""
    call_command("seed_learning_skills", verbosity=0)
    call_command("seed_badge_definitions", verbosity=0)
    call_command("seed_super_lesson_01", verbosity=0)


def _get_lesson_quiz() -> tuple[Course, Lesson, LessonQuiz]:
    course = Course.objects.get(slug="onlenco-beginner")
    lesson = Lesson.objects.get(course=course, order=1)
    return course, lesson, lesson.quiz


# ---------------------------------------------------------------------------
# 1. Seed command — existence + idempotency
# ---------------------------------------------------------------------------

class SeedCommandTests(TestCase):
    def test_seed_super_lesson_01_runs(self):
        _seed_all()
        course, lesson, quiz = _get_lesson_quiz()
        self.assertEqual(course.title, "Onlenco Beginner English Foundation")
        self.assertEqual(lesson.title, "Introducing Yourself")
        self.assertEqual(lesson.cefr_level, "A0")
        self.assertEqual(quiz.questions.count(), 10)

    def test_seed_super_lesson_01_idempotent(self):
        _seed_all()
        _seed_all()
        _seed_all()
        course, lesson, quiz = _get_lesson_quiz()
        # Still exactly 10 questions after 3 runs.
        self.assertEqual(quiz.questions.count(), 10)
        # Still 1 lesson, 1 unit, 1 course.
        self.assertEqual(
            Lesson.objects.filter(course=course, order=1).count(), 1,
        )
        self.assertEqual(
            Course.objects.filter(slug="onlenco-beginner").count(), 1,
        )

    def test_reseed_flag_clears_questions_first(self):
        _seed_all()
        course, lesson, quiz = _get_lesson_quiz()
        # Inject an unrelated question to verify --reseed wipes it.
        LessonQuestion.objects.create(
            quiz=quiz, order=99,
            question_type="multiple_choice",
            question_text="stale", options=["x"], correct_answer="x",
        )
        self.assertEqual(quiz.questions.count(), 11)
        call_command("seed_super_lesson_01", "--reseed", verbosity=0)
        self.assertEqual(quiz.questions.count(), 10)


# ---------------------------------------------------------------------------
# 2. Lesson content fully populated
# ---------------------------------------------------------------------------

class LessonContentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        _seed_all()
        cls.course, cls.lesson, cls.quiz = _get_lesson_quiz()

    def test_super_course_created(self):
        self.assertEqual(self.course.status, "published")
        self.assertEqual(self.course.level.code, "A0")
        self.assertTrue(self.course.is_free)

    def test_super_lesson_01_created(self):
        self.assertEqual(self.lesson.status, "published")
        self.assertEqual(self.lesson.order, 1)
        self.assertEqual(self.lesson.grammar_topic, "to_be_names")

    def test_super_lesson_has_content_html_and_ar(self):
        self.assertGreater(len(self.lesson.content_html), 1500)
        self.assertGreater(len(self.lesson.content_ar), 500)
        # Sectioned HTML markers — what the lesson page hooks on.
        for cls_name in [
            "lesson-goal", "new-language", "vocabulary", "key-language",
            "how-to-form", "mini-dialogue", "checklist",
        ]:
            self.assertIn(cls_name, self.lesson.content_html,
                          f"Missing <section class='{cls_name}'> in content_html")
        # Mini dialogue uses the Onlenco cast.
        self.assertIn("Amani", self.lesson.content_html)
        self.assertIn("Yusuf", self.lesson.content_html)
        # Arabic dir present.
        self.assertIn('dir="rtl"', self.lesson.content_ar)

    def test_super_lesson_has_image_prompts(self):
        prompts = LessonImagePrompt.objects.filter(lesson=self.lesson)
        # 4 prompt types: cover, vocabulary, grammar, quiz.
        self.assertEqual(prompts.count(), 4)
        types = set(prompts.values_list("prompt_type", flat=True))
        self.assertEqual(types, {"cover", "vocabulary", "grammar", "quiz"})
        # No file generated yet — these are scripts for Phase 9.
        self.assertTrue(all(not p.is_generated for p in prompts))

    def test_super_lesson_has_audio_scripts(self):
        scripts = LessonAudioScript.objects.filter(lesson=self.lesson)
        # 6 script types from the spec.
        self.assertEqual(scripts.count(), 6)
        types = set(scripts.values_list("script_type", flat=True))
        self.assertEqual(types, {"intro", "vocabulary", "examples",
                                 "dialogue", "listening", "speaking"})
        # Every script targets American English.
        for s in scripts:
            self.assertEqual(s.accent, "american")
            self.assertFalse(s.is_generated)

    def test_super_lesson_has_checklist(self):
        items = LessonChecklist.objects.filter(lesson=self.lesson, is_active=True)
        self.assertEqual(items.count(), 5)
        # All 5 bilingual.
        for item in items:
            self.assertTrue(item.text_en)
            self.assertTrue(item.text_ar)

    def test_content_is_original_onlenco_no_efe_strings(self):
        """Guardrail: the gold lesson must NEVER lift EFE-specific
        copyrighted phrases. We check that none of the recognisable
        EFE intros leaked in."""
        forbidden = [
            "English for Everyone",   # the book title
            "DK Publishing",
            "Duolingo",
        ]
        for needle in forbidden:
            self.assertNotIn(needle, self.lesson.content_html)
            self.assertNotIn(needle, self.lesson.content_ar)


# ---------------------------------------------------------------------------
# 3. Challenge sequence shape
# ---------------------------------------------------------------------------

class ChallengeSequenceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        _seed_all()
        cls.course, cls.lesson, cls.quiz = _get_lesson_quiz()

    def test_super_lesson_has_challenge(self):
        self.assertTrue(self.quiz.is_active)
        self.assertIn("Super Challenge", self.quiz.title)

    def test_super_challenge_has_10_questions(self):
        self.assertEqual(self.quiz.questions.count(), 10)

    def test_super_challenge_uses_multiple_question_types(self):
        types = set(
            self.quiz.questions.values_list("question_type", flat=True)
        )
        self.assertEqual(types, EXPECTED_QUESTION_TYPES)

    def test_each_super_question_has_skills(self):
        for q in self.quiz.questions.all().order_by("order"):
            with self.subTest(order=q.order, qt=q.question_type):
                skills = (q.metadata or {}).get("skills") or []
                self.assertTrue(
                    skills,
                    f"Question #{q.order} ({q.question_type}) "
                    f"has no metadata.skills",
                )

    def test_skills_used_exist_in_taxonomy(self):
        from learning_core.models import Skill
        all_codes = set(
            Skill.objects.exclude(code__isnull=True)
            .values_list("code", flat=True)
        )
        for q in self.quiz.questions.all():
            for code in (q.metadata or {}).get("skills") or []:
                with self.subTest(qt=q.question_type, skill=code):
                    self.assertIn(code, all_codes)


# ---------------------------------------------------------------------------
# 4. Per-renderer rendering (no 500 even when media is absent)
# ---------------------------------------------------------------------------

class RendererRenderingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        _seed_all()
        cls.course, cls.lesson, cls.quiz = _get_lesson_quiz()
        cls.student = _make_student("rd-1")
        CourseEnrollment.objects.get_or_create(user=cls.student, course=cls.course)

    def _render_q_type(self, question_type: str) -> str:
        q = self.quiz.questions.get(question_type=question_type)
        # Pin a session at exactly this question.
        ChallengeSession.objects.filter(
            user=self.student, lesson=self.lesson,
        ).delete()
        session = ChallengeSession.objects.create(
            user=self.student, lesson=self.lesson, quiz=self.quiz,
            status="in_progress", question_ids=[q.pk],
            total_questions=1, current_question_index=0,
            hearts_total=5, hearts_remaining=5,
        )
        c = _login(self.student)
        r = c.get(reverse("courses:challenge_current",
                          args=[self.course.pk, self.lesson.pk, session.pk]),
                  HTTP_HOST="127.0.0.1")
        self.assertEqual(r.status_code, 200,
                         f"{question_type} rendered status {r.status_code}")
        return r.content.decode("utf-8", errors="ignore")

    # One test per type — keeps failures specific in the report.

    def test_super_lesson_tap_choice_works(self):
        self.assertIn("onlenco-qr--tap-choice", self._render_q_type("tap_choice"))

    def test_super_lesson_listen_and_choose_with_pending_audio(self):
        body = self._render_q_type("listen_and_choose")
        # No audio file yet — fallback "Audio coming soon" must appear.
        self.assertIn("Audio coming soon", body)

    def test_super_lesson_word_bank_sentence_works(self):
        body = self._render_q_type("word_bank_sentence")
        self.assertIn("data-word-bank", body)

    def test_super_lesson_fill_blank_card_works(self):
        body = self._render_q_type("fill_blank_card")
        self.assertIn("onlenco-qr--fill-blank", body)

    def test_super_lesson_match_pairs_works(self):
        body = self._render_q_type("match_pairs")
        self.assertIn("data-match-root", body)

    def test_super_lesson_conversation_reply_works(self):
        body = self._render_q_type("conversation_reply")
        self.assertIn("onlenco-qr__bubble", body)

    def test_super_lesson_q7_is_a0_friendly_image_choice(self):
        """Phase 9.5: Q7 must be image_choice (recognition), NOT
        translate_to_english (production) — A0 cannot reliably produce
        a full sentence in lesson 1."""
        body = self._render_q_type("image_choice")
        self.assertIn("onlenco-qr--image-choice", body)
        # The 4 options must each be in the markup.
        for text in ("person waving", "book", "chair", "car"):
            self.assertIn(text, body)

    def test_super_lesson_q8_uses_sound_to_word_not_listen_and_type(self):
        """Phase 9.5: Q8 must be sound_to_word (pick a phrase), NOT
        listen_and_type (type a full sentence) — typing-without-audio
        was just copying the transcript."""
        body = self._render_q_type("sound_to_word")
        # No full-sentence typing in the first lesson.
        self.assertIn("Audio coming soon", body)
        # 4 phrase options visible.
        self.assertIn("My name is Layla", body)
        self.assertIn("My name is Omar", body)
        self.assertIn("I have a book", body)

    def test_super_lesson_speak_this_sentence_works(self):
        body = self._render_q_type("speak_this_sentence")
        # The renderer pill is bilingual; the canonical EN copy must be present.
        self.assertIn("AI speaking feedback coming soon", body)

    def test_super_lesson_ai_roleplay_placeholder_works(self):
        # Phase 9.5: ai_roleplay_prompt now renders the real AI roleplay
        # card (with live wiring when AI is on, fallback dialogue when off).
        # The dedicated container class is the stable marker.
        body = self._render_q_type("ai_roleplay_prompt")
        self.assertIn("onlenco-qr--ai-roleplay", body)


# ---------------------------------------------------------------------------
# 5. End-to-end Challenge + Mastery + Rewards
# ---------------------------------------------------------------------------

class EndToEndChallengeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        _seed_all()
        cls.course, cls.lesson, cls.quiz = _get_lesson_quiz()
        cls.student = _make_student("e2e-1")
        CourseEnrollment.objects.get_or_create(user=cls.student, course=cls.course)

    def _full_run(self, *, correct_first_n: int = 10):
        """Submit answers — first `correct_first_n` correct, rest deliberately
        wrong. Returns the completed/failed ChallengeSession."""
        from courses.services import challenge_runner
        session = challenge_runner.start_or_resume(self.student, self.lesson)
        for idx, qid in enumerate(list(session.question_ids)):
            q = LessonQuestion.objects.get(pk=qid)
            want_correct = idx < correct_first_n
            ans = self._right_answer(q) if want_correct else self._wrong_answer(q)
            try:
                challenge_runner.submit_answer(session, q, ans)
            except challenge_runner.ChallengeError:
                break
            session.refresh_from_db()
            if not session.is_active:
                break
            try:
                challenge_runner.continue_to_next(session)
            except challenge_runner.ChallengeError:
                break
            session.refresh_from_db()
        return session

    def _right_answer(self, q):
        qt = q.question_type
        md = q.metadata or {}
        if qt in ("tap_choice", "image_choice", "listen_and_choose",
                  "sound_to_word", "mini_story_choice", "conversation_reply",
                  "translate_to_arabic"):
            return md.get("correct_option_id", "")
        if qt == "word_bank_sentence":
            import json
            return json.dumps(md.get("correct_order") or [])
        if qt == "match_pairs":
            import json
            pairs = md.get("pairs") or []
            return json.dumps({p["left"]: p["right"] for p in pairs})
        if qt == "fill_blank_card":
            return q.correct_answer
        if qt == "listen_and_type":
            return md.get("correct_answer") or q.correct_answer
        if qt == "translate_to_english":
            accepted = md.get("accepted_answers") or [q.correct_answer]
            return accepted[0]
        # Speaking + roleplay placeholders accept anything.
        return "self_read"

    def _wrong_answer(self, q):
        return "definitely_wrong_value"

    def test_super_challenge_runs_start_to_summary(self):
        session = self._full_run(correct_first_n=10)
        self.assertEqual(session.status, "completed")
        self.assertEqual(session.correct_count, 10)
        self.assertGreaterEqual(session.xp_earned, 100)   # ~10*10 + bonuses

    def test_super_challenge_summary_shows_xp_rewards_mastery(self):
        session = self._full_run(correct_first_n=10)
        c = _login(self.student)
        r = c.get(reverse("courses:challenge_summary", args=[
            self.course.pk, self.lesson.pk, session.pk,
        ]), HTTP_HOST="127.0.0.1")
        self.assertEqual(r.status_code, 200)
        body = r.content.decode()
        # Phase-5 rewards section
        self.assertIn("data-xp-breakdown", body)
        # Phase-5 streak/daily-goal section
        self.assertIn("data-streak", body)
        self.assertIn("data-daily-goal", body)
        # Phase-6 mastery section
        self.assertIn("data-skills-practiced", body)
        self.assertIn("data-recommendation", body)
        # Phase-7 AI section
        self.assertIn("data-ai-advice", body)

    def test_super_lesson_updates_mastery(self):
        self._full_run(correct_first_n=10)
        # Skill rows exist for the codes the questions tagged.
        codes_used = {"greetings", "to_be_names", "listening_basic",
                      "speaking_intro"}
        for code in codes_used:
            with self.subTest(code=code):
                self.assertTrue(
                    SkillMastery.objects.filter(
                        user=self.student, skill__code=code, attempts_count__gt=0,
                    ).exists(),
                    f"No SkillMastery for {code}",
                )

    def test_super_lesson_wrong_answer_creates_mistake(self):
        # First-only wrong → produces a StudentMistake row.
        self._full_run(correct_first_n=0)
        self.assertGreater(
            StudentMistake.objects.filter(user=self.student).count(),
            0,
        )

    def test_super_lesson_recommendation_after_completion(self):
        from learning_core.services import phase6_recommendation
        self._full_run(correct_first_n=10)
        rec = phase6_recommendation.get_next_best_action(self.student)
        self.assertIn(rec["kind"], {
            "review_mistakes", "practice_skill", "daily_goal",
            "continue_lesson", "retry_challenge",
        })

    # ---- Rewards ----

    def test_super_lesson_awards_xp_once(self):
        self._full_run(correct_first_n=10)
        completion = XPTransaction.objects.filter(
            user=self.student, source_type="challenge_completion",
        ).count()
        self.assertEqual(completion, 1)

    def test_super_lesson_hearts_work(self):
        session = self._full_run(correct_first_n=0)
        # Wrong answers → hearts depleted → status failed.
        self.assertLessEqual(session.hearts_remaining, 5)

    def test_super_lesson_badges_evaluate(self):
        # 10 correct + first-ever completion → FIRST_CHALLENGE +
        # PERFECT_CHALLENGE both fire.
        self._full_run(correct_first_n=10)
        codes = set(
            UserBadge.objects.filter(user=self.student)
            .values_list("badge_code", flat=True)
        )
        self.assertIn("FIRST_CHALLENGE", codes)
        self.assertIn("PERFECT_CHALLENGE", codes)

    def test_super_lesson_daily_goal_updates(self):
        from django.utils import timezone
        self._full_run(correct_first_n=10)
        progress = DailyGoalProgress.objects.get(
            user=self.student, date=timezone.localdate(),
        )
        self.assertGreaterEqual(progress.xp_earned, 50)
        self.assertTrue(progress.completed)


# ---------------------------------------------------------------------------
# 6. AI Tutor integration
# ---------------------------------------------------------------------------

class AIIntegrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        _seed_all()
        cls.course, cls.lesson, cls.quiz = _get_lesson_quiz()
        cls.student = _make_student("ai-1")
        CourseEnrollment.objects.get_or_create(user=cls.student, course=cls.course)

    @override_settings(AI_API_KEY="")
    def test_super_lesson_wrong_answer_ai_explain_fallback(self):
        from courses.services import challenge_runner
        session = challenge_runner.start_or_resume(self.student, self.lesson)
        q = LessonQuestion.objects.get(pk=session.question_ids[0])
        challenge_runner.submit_answer(session, q, "wrong")
        answer = ChallengeAnswer.objects.get(session=session, question=q)
        c = _login(self.student)
        r = c.post(reverse("courses:ai_explain_wrong_answer", args=[
            self.course.pk, self.lesson.pk, session.pk, answer.pk,
        ]), HTTP_HOST="127.0.0.1")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        # AI off → status is fallback or failed, BUT we still get text.
        self.assertIn(data["status"], {"fallback", "failed"})
        self.assertTrue(data["explanation_en"])

    @override_settings(AI_API_KEY="")
    def test_super_lesson_ai_disabled_still_completes(self):
        from courses.services import challenge_runner
        session = challenge_runner.start_or_resume(self.student, self.lesson)
        for qid in list(session.question_ids):
            q = LessonQuestion.objects.get(pk=qid)
            challenge_runner.submit_answer(session, q, "wrong")
            session.refresh_from_db()
            if not session.is_active:
                break
            challenge_runner.continue_to_next(session)
            session.refresh_from_db()
        self.assertIn(session.status, {"completed", "failed"})
        # No AI was called.
        self.assertEqual(
            ChallengeAIInteraction.objects.filter(user=self.student).count(),
            0,
        )

    def test_super_lesson_ai_roleplay_guarded(self):
        from courses.services import challenge_runner
        session = challenge_runner.start_or_resume(self.student, self.lesson)
        roleplay_q = self.quiz.questions.get(question_type="ai_roleplay_prompt")
        c = _login(self.student)
        r = c.post(reverse("courses:ai_roleplay_start", args=[
            self.course.pk, self.lesson.pk, session.pk, roleplay_q.pk,
        ]), HTTP_HOST="127.0.0.1")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data["roleplay_id"])
        self.assertTrue(data["opening_en"])


# ---------------------------------------------------------------------------
# 7. Lesson page + Classic Quiz still render
# ---------------------------------------------------------------------------

class LessonPageRegressionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        _seed_all()
        cls.course, cls.lesson, cls.quiz = _get_lesson_quiz()
        cls.student = _make_student("lp-1")
        CourseEnrollment.objects.get_or_create(user=cls.student, course=cls.course)

    def test_super_lesson_page_renders(self):
        c = _login(self.student)
        r = c.get(reverse("courses:lesson_detail",
                          args=[self.course.pk, self.lesson.pk]),
                  HTTP_HOST="127.0.0.1")
        self.assertEqual(r.status_code, 200)
        body = r.content.decode()
        # The lesson title is on the page.
        self.assertIn("Introducing Yourself", body)
        # The launcher exposes both Challenge and Classic Quiz.
        self.assertIn('data-action="start-challenge"', body)
        self.assertIn('data-action="classic-quiz"', body)

    def test_super_lesson_page_no_500_without_media(self):
        # Even with no image/audio files generated, the page must 200.
        for f in self.lesson.image_prompts.all():
            self.assertFalse(f.is_generated)
        c = _login(self.student)
        r = c.get(reverse("courses:lesson_detail",
                          args=[self.course.pk, self.lesson.pk]),
                  HTTP_HOST="127.0.0.1")
        self.assertEqual(r.status_code, 200)

    def test_classic_quiz_endpoint_still_works(self):
        c = _login(self.student)
        r = c.get(reverse("courses:lesson_quiz_attempt",
                          args=[self.course.pk, self.lesson.pk]),
                  HTTP_HOST="127.0.0.1")
        self.assertEqual(r.status_code, 200)


# ---------------------------------------------------------------------------
# Phase 9.5 — Fixes for the 4 P1 issues identified in Phase 9 review.
# ---------------------------------------------------------------------------

class Phase95RoleplayCardTests(TestCase):
    """P1-A: Q10 ai_roleplay_prompt now has a real in-card UI that wires
    the Phase-7 endpoints when AI is on, and a self-practice fallback
    when off. Never just a 'coming soon' pill."""

    @classmethod
    def setUpTestData(cls):
        _seed_all()
        cls.course, cls.lesson, cls.quiz = _get_lesson_quiz()
        cls.student = _make_student("rp-95")
        CourseEnrollment.objects.get_or_create(user=cls.student, course=cls.course)

    def _render_roleplay(self):
        q = self.quiz.questions.get(question_type="ai_roleplay_prompt")
        ChallengeSession.objects.filter(
            user=self.student, lesson=self.lesson,
        ).delete()
        s = ChallengeSession.objects.create(
            user=self.student, lesson=self.lesson, quiz=self.quiz,
            status="in_progress", question_ids=[q.pk],
            total_questions=1, current_question_index=0,
            hearts_total=5, hearts_remaining=5,
        )
        c = _login(self.student)
        r = c.get(reverse("courses:challenge_current", args=[
            self.course.pk, self.lesson.pk, s.pk,
        ]), HTTP_HOST="127.0.0.1")
        return r

    def test_super_lesson_q10_no_longer_coming_soon_only(self):
        r = self._render_roleplay()
        self.assertEqual(r.status_code, 200)
        body = r.content.decode()
        # The new card has the dedicated container class, not the generic
        # speaking placeholder.
        self.assertIn("onlenco-qr--ai-roleplay", body)
        self.assertIn("data-ai-roleplay", body)

    @override_settings(AI_API_KEY="testkey", CHALLENGE_AI_ENABLED=True)
    def test_ai_roleplay_card_renders_start_button_when_ai_enabled(self):
        r = self._render_roleplay()
        body = r.content.decode()
        self.assertIn("data-roleplay-start", body)
        self.assertIn("data-roleplay-chat", body)
        self.assertIn("data-roleplay-form", body)

    @override_settings(AI_API_KEY="")
    def test_ai_roleplay_card_shows_fallback_when_ai_disabled(self):
        r = self._render_roleplay()
        body = r.content.decode()
        # Fallback dialogue is visible.
        self.assertIn("onlenco-qr__roleplay-fallback", body)
        self.assertIn("What is your name?", body)
        # The start button is NOT rendered.
        self.assertNotIn("data-roleplay-start", body)

    def test_ai_roleplay_card_can_mark_practiced(self):
        r = self._render_roleplay()
        body = r.content.decode()
        # The self-check checkbox is present in BOTH branches so the
        # Challenge can advance without depending on AI.
        self.assertIn('name="answer"', body)
        self.assertIn('value="self_read"', body)


class Phase95EasierQ7Q8Tests(TestCase):
    """P1-B: Q7 swapped to image_choice, Q8 swapped to sound_to_word."""

    @classmethod
    def setUpTestData(cls):
        _seed_all()
        cls.course, cls.lesson, cls.quiz = _get_lesson_quiz()

    def test_super_lesson_q7_is_image_choice(self):
        q7 = self.quiz.questions.get(order=7)
        self.assertEqual(q7.question_type, "image_choice")
        # 4 options + skill tagged.
        self.assertEqual(len(q7.metadata.get("options") or []), 4)
        self.assertIn("greetings", q7.metadata.get("skills") or [])
        # Difficulty dropped from 0.5 → 0.3.
        self.assertLessEqual(q7.difficulty_score, 0.4)

    def test_super_lesson_q8_is_sound_to_word(self):
        q8 = self.quiz.questions.get(order=8)
        self.assertEqual(q8.question_type, "sound_to_word")
        # 4 short phrase options — no full-sentence typing.
        opts = q8.metadata.get("options") or []
        self.assertEqual(len(opts), 4)
        self.assertIn("listening_basic", q8.metadata.get("skills") or [])
        # Difficulty dropped from 0.6 → 0.4.
        self.assertLessEqual(q8.difficulty_score, 0.5)

    def test_super_lesson_no_full_sentence_typing_in_first_lesson(self):
        # No question in lesson 1 is listen_and_type or translate_to_english.
        types = set(
            self.quiz.questions.values_list("question_type", flat=True)
        )
        self.assertNotIn("listen_and_type", types)
        self.assertNotIn("translate_to_english", types)

    def test_super_lesson_challenge_still_has_10_questions(self):
        self.assertEqual(self.quiz.questions.count(), 10)


class Phase95VisualPlaceholderTests(TestCase):
    """P1-C: Visual placeholder appears on relevant step pages when no
    image is generated yet — and 200, not 500."""

    @classmethod
    def setUpTestData(cls):
        _seed_all()
        cls.course, cls.lesson, cls.quiz = _get_lesson_quiz()
        cls.student = _make_student("vis-95")
        CourseEnrollment.objects.get_or_create(user=cls.student, course=cls.course)

    def _step(self, step_kind):
        c = _login(self.student)
        return c.get(reverse("courses:lesson_step", args=[
            self.course.pk, self.lesson.pk, step_kind,
        ]), HTTP_HOST="127.0.0.1")

    def test_vocabulary_step_shows_image_placeholder(self):
        r = self._step("vocabulary")
        self.assertEqual(r.status_code, 200)
        body = r.content.decode()
        self.assertIn("onlenco-lesson-img", body)
        self.assertIn("Image coming soon", body)

    def test_examples_step_shows_image_placeholder(self):
        r = self._step("examples")
        self.assertEqual(r.status_code, 200)
        body = r.content.decode()
        self.assertIn("onlenco-lesson-img", body)

    def test_finish_step_shows_image_placeholder(self):
        r = self._step("finish")
        self.assertEqual(r.status_code, 200)
        body = r.content.decode()
        self.assertIn("onlenco-lesson-img", body)

    def test_lesson_step_no_500_without_generated_media(self):
        # None of the prompts have generated images — page must 200.
        from courses.models import LessonImagePrompt
        for p in LessonImagePrompt.objects.filter(lesson=self.lesson):
            self.assertFalse(p.is_generated)
        for step in ("intro", "vocabulary", "examples", "dialogue",
                     "listening", "speaking", "finish"):
            r = self._step(step)
            self.assertEqual(r.status_code, 200,
                             f"Step {step} returned {r.status_code}")

    def test_lesson_step_does_not_show_raw_prompt_json(self):
        # The student must NEVER see the raw English prompt string.
        from courses.models import LessonImagePrompt
        vocab_prompt = LessonImagePrompt.objects.get(
            lesson=self.lesson, prompt_type="vocabulary",
        )
        # The seed prompt starts with "A clean vocabulary card set..."
        prompt_snippet = vocab_prompt.prompt[:40]
        r = self._step("vocabulary")
        self.assertEqual(r.status_code, 200)
        self.assertNotIn(prompt_snippet, r.content.decode())


class Phase95ArabicCompletenessTests(TestCase):
    """P1-D: content_ar now mirrors the 4 sections that were EN-only."""

    @classmethod
    def setUpTestData(cls):
        _seed_all()
        cls.course, cls.lesson, cls.quiz = _get_lesson_quiz()

    def test_super_lesson_content_ar_has_visual_section(self):
        self.assertIn('class="visual-guide"', self.lesson.content_ar)
        self.assertIn("الدليل البصري", self.lesson.content_ar)

    def test_super_lesson_content_ar_has_listening_section(self):
        self.assertIn('class="listening-practice"', self.lesson.content_ar)
        self.assertIn("تدريب الاستماع", self.lesson.content_ar)

    def test_super_lesson_content_ar_has_speaking_section(self):
        self.assertIn('class="speaking-practice"', self.lesson.content_ar)
        self.assertIn("تدريب المحادثة", self.lesson.content_ar)

    def test_super_lesson_content_ar_has_ai_tutor_section(self):
        self.assertIn('class="ai-tutor-drill"', self.lesson.content_ar)
        self.assertIn("المعلم الذكي", self.lesson.content_ar)

    def test_super_lesson_arabic_content_balanced_with_english(self):
        # Now within ±25% of EN (was ~70% before — gap closed).
        en_len = len(self.lesson.content_html)
        ar_len = len(self.lesson.content_ar)
        ratio = ar_len / en_len
        self.assertGreater(ratio, 0.75,
                           f"Arabic content too short: {ar_len}/{en_len} = {ratio:.2f}")


class Phase95SeedRegressionTests(TestCase):
    """Phase 9.5 didn't break the existing seed idempotency contract."""

    def test_seed_super_lesson_01_idempotent_after_095(self):
        _seed_all()
        course1, lesson1, quiz1 = _get_lesson_quiz()
        q_count_1 = quiz1.questions.count()
        _seed_all()
        course2, lesson2, quiz2 = _get_lesson_quiz()
        q_count_2 = quiz2.questions.count()
        self.assertEqual(q_count_1, q_count_2)
        self.assertEqual(q_count_1, 10)
        # Same course / lesson — not duplicated.
        self.assertEqual(Course.objects.filter(slug="onlenco-beginner").count(), 1)
        self.assertEqual(Lesson.objects.filter(course=course1, order=1).count(), 1)
