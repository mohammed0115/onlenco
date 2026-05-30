"""Phase 6 — Adaptive Learning / Mastery Engine.

Covers:
  * Skill taxonomy seeding + uniqueness.
  * skill_resolver — metadata, lesson inference, fallback.
  * StudentSkillMastery — score deltas, confidence band, idempotency.
  * StudentMistake — creation + upsert + classification.
  * Review scheduler rules + due queue.
  * Smart review queue ordering.
  * Recommendation engine — all 5 branches.
  * Challenge integration — mastery + mistakes update + idempotency.
  * Summary page surfaces skills practiced + recommendation.
  * Regression — Challenge/Rewards/UI suites still pass.
"""
from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from courses.models import (
    ChallengeAnswer, ChallengeSession, Course, CourseEnrollment,
    CourseLevel, CourseUnit, Lesson, LessonQuestion, LessonQuiz,
)
from learning_core.models import (
    MasteryEvent, Skill, SkillMastery, StudentMistake, confidence_for,
)
from learning_core.services import (
    mastery_service, mistake_classifier, phase6_recommendation,
    review_scheduler, skill_resolver, smart_review_service,
)


User = get_user_model()


def _make_user(name="ph6") -> User:
    u = User.objects.create_user(
        username=name, password="pw", email=f"{name}@onlenco.test",
    )
    if hasattr(u, "profile"):
        u.profile.email_verified = True
        u.profile.subscription_status = "active"
        u.profile.preferred_language = "en"
        u.profile.save()
    return u


def _make_course(slug="ph6") -> tuple[Course, CourseUnit, Lesson, LessonQuiz]:
    level, _ = CourseLevel.objects.get_or_create(
        code="C0", defaults={"name": "Ph6 tests", "order": 99},
    )
    teacher = _make_user(f"teacher-{slug}")
    course = Course.objects.create(
        title=f"Ph6 {slug}", slug=slug, level=level,
        teacher=teacher, created_by=teacher,
        status="published", is_active=True,
    )
    unit = CourseUnit.objects.create(course=course, title="U", order=1)
    lesson = Lesson.objects.create(
        course=course, unit=unit, title="L", order=1,
        status="published", is_active=True,
        grammar_topic="To Be Names",
    )
    quiz = LessonQuiz.objects.create(lesson=lesson, title="Q")
    return course, unit, lesson, quiz


def _make_question(quiz, *, question_type="tap_choice",
                   metadata=None, difficulty=0.5, **kw) -> LessonQuestion:
    return LessonQuestion.objects.create(
        quiz=quiz,
        order=kw.get("order", LessonQuestion.objects.filter(quiz=quiz).count() + 1),
        question_type=question_type,
        question_text=kw.get("question_text", "Pick one"),
        options=kw.get("options", ["a", "b"]),
        metadata=metadata or {},
        correct_answer=kw.get("correct_answer", "a"),
        difficulty_score=difficulty,
    )


def _make_session(user, lesson, quiz, qids: list[int]) -> ChallengeSession:
    # Retire any prior active sessions for the same (user, lesson) —
    # the model has a partial UNIQUE constraint preventing two active.
    ChallengeSession.objects.filter(
        user=user, lesson=lesson,
        status__in=("started", "in_progress"),
    ).update(status="abandoned")
    return ChallengeSession.objects.create(
        user=user, lesson=lesson, quiz=quiz,
        status="in_progress", question_ids=qids,
        total_questions=len(qids), current_question_index=0,
        hearts_total=5, hearts_remaining=5,
    )


def _make_answer(session, question, *, is_correct=True, score=None) -> ChallengeAnswer:
    if score is None:
        score = 1.0 if is_correct else 0.0
    return ChallengeAnswer.objects.create(
        session=session, question=question,
        user_answer="hello",
        is_correct=is_correct,
        score=score,
        xp_awarded=10 if is_correct else 0,
        heart_lost=not is_correct,
    )


# ---------------------------------------------------------------------------
# 1. Skill taxonomy + seed command
# ---------------------------------------------------------------------------

class SkillTaxonomyTests(TestCase):
    def test_seed_learning_skills_idempotent(self):
        call_command("seed_learning_skills", verbosity=0)
        n_first = Skill.objects.count()
        call_command("seed_learning_skills", verbosity=0)
        n_second = Skill.objects.count()
        self.assertEqual(n_first, n_second)
        # 51 skills (50 named + fallback).
        self.assertGreaterEqual(n_second, 51)

    def test_skill_codes_unique(self):
        call_command("seed_learning_skills", verbosity=0)
        codes = list(
            Skill.objects.exclude(code__isnull=True).values_list("code", flat=True)
        )
        self.assertEqual(len(codes), len(set(codes)))

    def test_confidence_for_bands(self):
        self.assertEqual(confidence_for(0), "new")
        self.assertEqual(confidence_for(20), "new")
        self.assertEqual(confidence_for(21), "learning")
        self.assertEqual(confidence_for(45), "learning")
        self.assertEqual(confidence_for(46), "improving")
        self.assertEqual(confidence_for(70), "improving")
        self.assertEqual(confidence_for(71), "strong")
        self.assertEqual(confidence_for(89), "strong")
        self.assertEqual(confidence_for(90), "mastered")
        self.assertEqual(confidence_for(100), "mastered")


# ---------------------------------------------------------------------------
# 2. skill_resolver
# ---------------------------------------------------------------------------

class SkillResolverTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_learning_skills", verbosity=0)
        cls.course, cls.unit, cls.lesson, cls.quiz = _make_course("res")

    def test_resolver_uses_explicit_skills_list(self):
        q = _make_question(self.quiz, metadata={"skills": ["greetings", "to_be_names"]})
        skills = skill_resolver.get_question_skills(q)
        self.assertEqual({s.code for s in skills}, {"greetings", "to_be_names"})

    def test_resolver_uses_single_skill_key(self):
        q = _make_question(self.quiz, metadata={"skill": "greetings"})
        skills = skill_resolver.get_question_skills(q)
        self.assertEqual({s.code for s in skills}, {"greetings"})

    def test_resolver_falls_back_to_lesson_grammar_topic(self):
        # The lesson's grammar_topic="To Be Names" → slug "to_be_names" → seeded.
        q = _make_question(self.quiz, metadata={})
        primary = skill_resolver.get_primary_skill(q)
        self.assertIsNotNone(primary)
        self.assertEqual(primary.code, "to_be_names")

    def test_resolver_falls_back_to_general_beginner(self):
        # Lesson with NO grammar/vocabulary topic + question with no metadata.
        teacher = _make_user("solo-teacher")
        course = Course.objects.create(
            title="solo", slug="solo", level=self.course.level,
            teacher=teacher, created_by=teacher,
            status="published", is_active=True,
        )
        unit = CourseUnit.objects.create(course=course, title="U", order=1)
        lesson = Lesson.objects.create(
            course=course, unit=unit, title="L", order=1,
            status="published", is_active=True,
        )
        quiz = LessonQuiz.objects.create(lesson=lesson, title="Q")
        q = _make_question(quiz, metadata={})
        skills = skill_resolver.get_question_skills(q)
        self.assertEqual({s.code for s in skills}, {"general_beginner"})

    def test_validate_question_skills_flags_unknown(self):
        q = _make_question(self.quiz, metadata={"skills": ["nope_not_real"]})
        issues = skill_resolver.validate_question_skills(q)
        self.assertTrue(any("unknown_skill_codes" in i for i in issues))


# ---------------------------------------------------------------------------
# 3. Mastery deltas + idempotency
# ---------------------------------------------------------------------------

class MasteryServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_learning_skills", verbosity=0)
        cls.course, cls.unit, cls.lesson, cls.quiz = _make_course("mas")
        cls.student = _make_user("mas-s1")
        CourseEnrollment.objects.get_or_create(user=cls.student, course=cls.course)

    def _new_session_and_question(self, *, metadata=None, difficulty=0.5):
        q = _make_question(self.quiz, metadata=metadata or {"skill": "greetings"},
                           difficulty=difficulty)
        s = _make_session(self.student, self.lesson, self.quiz, [q.pk])
        return s, q

    def test_mastery_created_after_first_correct_answer(self):
        s, q = self._new_session_and_question()
        a = _make_answer(s, q, is_correct=True)
        mastery_service.process_challenge_answer(a)
        mastery = SkillMastery.objects.get(user=self.student, skill__code="greetings")
        self.assertGreater(mastery.mastery_score, 0)
        self.assertEqual(mastery.correct_count, 1)
        self.assertEqual(mastery.attempts_count, 1)

    def test_correct_answer_increases_mastery_easy(self):
        s, q = self._new_session_and_question(difficulty=0.2)  # easy
        a = _make_answer(s, q, is_correct=True)
        mastery_service.process_challenge_answer(a)
        mastery = SkillMastery.objects.get(user=self.student, skill__code="greetings")
        self.assertEqual(mastery.mastery_score, 5.0)

    def test_correct_answer_increases_mastery_hard(self):
        s, q = self._new_session_and_question(difficulty=0.9)  # hard
        a = _make_answer(s, q, is_correct=True)
        mastery_service.process_challenge_answer(a)
        mastery = SkillMastery.objects.get(user=self.student, skill__code="greetings")
        self.assertEqual(mastery.mastery_score, 12.0)

    def test_wrong_answer_decreases_mastery(self):
        # Seed the mastery first.
        s, q = self._new_session_and_question(difficulty=0.5)
        a = _make_answer(s, q, is_correct=True)
        mastery_service.process_challenge_answer(a)
        # Now an incorrect answer on a fresh question (same skill).
        s2 = _make_session(self.student, self.lesson, self.quiz, [q.pk])
        q2 = _make_question(self.quiz, metadata={"skill": "greetings"}, difficulty=0.5)
        a2 = _make_answer(s2, q2, is_correct=False)
        mastery_service.process_challenge_answer(a2)
        mastery = SkillMastery.objects.get(user=self.student, skill__code="greetings")
        # 8 (correct medium) - 6 (wrong medium) = 2
        self.assertEqual(mastery.mastery_score, 2.0)

    def test_mastery_never_below_zero(self):
        s, q = self._new_session_and_question()
        a = _make_answer(s, q, is_correct=False)
        mastery_service.process_challenge_answer(a)
        mastery = SkillMastery.objects.get(user=self.student, skill__code="greetings")
        self.assertEqual(mastery.mastery_score, 0.0)

    def test_mastery_never_above_100(self):
        # 14 correct hard answers (12 each) = 168 → must cap at 100.
        for i in range(14):
            s, q = self._new_session_and_question(difficulty=0.9)
            a = _make_answer(s, q, is_correct=True)
            mastery_service.process_challenge_answer(a)
        mastery = SkillMastery.objects.get(user=self.student, skill__code="greetings")
        self.assertEqual(mastery.mastery_score, 100.0)

    def test_confidence_level_updates(self):
        # Land in "improving" (46-70) after several correct mediums.
        for _ in range(7):  # 7 * 8 = 56
            s, q = self._new_session_and_question(difficulty=0.5)
            a = _make_answer(s, q, is_correct=True)
            mastery_service.process_challenge_answer(a)
        mastery = SkillMastery.objects.get(user=self.student, skill__code="greetings")
        self.assertEqual(mastery.confidence_level, "improving")

    def test_mastery_not_processed_twice_for_same_answer(self):
        s, q = self._new_session_and_question(difficulty=0.5)
        a = _make_answer(s, q, is_correct=True)
        first  = mastery_service.process_challenge_answer(a)
        second = mastery_service.process_challenge_answer(a)
        self.assertTrue(first)
        self.assertFalse(second)
        mastery = SkillMastery.objects.get(user=self.student, skill__code="greetings")
        # Score is 8 (NOT 16) because the second call was a no-op.
        self.assertEqual(mastery.mastery_score, 8.0)
        self.assertEqual(mastery.attempts_count, 1)
        self.assertEqual(MasteryEvent.objects.filter(challenge_answer=a).count(), 1)

    def test_streak_counters_update(self):
        s, q = self._new_session_and_question()
        mastery_service.process_challenge_answer(_make_answer(s, q, is_correct=True))
        s2, q2 = self._new_session_and_question()
        mastery_service.process_challenge_answer(_make_answer(s2, q2, is_correct=True))
        mastery = SkillMastery.objects.get(user=self.student, skill__code="greetings")
        self.assertEqual(mastery.current_streak_correct, 2)
        self.assertEqual(mastery.current_streak_wrong, 0)
        # A wrong one resets the correct streak and starts a wrong streak.
        s3, q3 = self._new_session_and_question()
        mastery_service.process_challenge_answer(_make_answer(s3, q3, is_correct=False))
        mastery.refresh_from_db()
        self.assertEqual(mastery.current_streak_correct, 0)
        self.assertEqual(mastery.current_streak_wrong, 1)


# ---------------------------------------------------------------------------
# 4. Mistake tracking + classifier
# ---------------------------------------------------------------------------

class MistakeTrackingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_learning_skills", verbosity=0)
        cls.course, cls.unit, cls.lesson, cls.quiz = _make_course("mst")
        cls.student = _make_user("mst-s1")
        CourseEnrollment.objects.get_or_create(user=cls.student, course=cls.course)

    def test_mistake_type_classified_by_question_type(self):
        for qt, expected in [
            ("word_bank_sentence", "word_order"),
            ("listen_and_type",    "listening"),
            ("tap_choice",         "wrong_choice"),
            ("translate_to_english","translation"),
            ("nope_unknown_type",  "unknown"),
        ]:
            with self.subTest(qt=qt):
                kind, _sev = mistake_classifier.classify(
                    type("Q", (), {"question_type": qt})()
                )
                self.assertEqual(kind, expected)

    def test_wrong_answer_creates_mistake(self):
        q = _make_question(self.quiz, metadata={"skill": "greetings"},
                           question_type="tap_choice")
        s = _make_session(self.student, self.lesson, self.quiz, [q.pk])
        a = _make_answer(s, q, is_correct=False)
        mastery_service.process_challenge_answer(a)
        mistake = StudentMistake.objects.get(user=self.student, question=q)
        self.assertEqual(mistake.mistake_type, "wrong_choice")
        self.assertEqual(mistake.review_count, 0)
        self.assertIsNotNone(mistake.next_review_at)

    def test_repeated_wrong_answer_updates_existing_mistake(self):
        q = _make_question(self.quiz, metadata={"skill": "greetings"})
        s1 = _make_session(self.student, self.lesson, self.quiz, [q.pk])
        mastery_service.process_challenge_answer(_make_answer(s1, q, is_correct=False))
        s2 = _make_session(self.student, self.lesson, self.quiz, [q.pk])
        mastery_service.process_challenge_answer(_make_answer(s2, q, is_correct=False))
        # Only ONE mistake row — the second wrong bumped review_count.
        rows = StudentMistake.objects.filter(user=self.student, question=q)
        self.assertEqual(rows.count(), 1)
        self.assertEqual(rows.first().review_count, 1)

    def test_correct_answer_can_mark_mistake_improved(self):
        q = _make_question(self.quiz, metadata={"skill": "greetings"})
        # First answer wrong → mistake created.
        s1 = _make_session(self.student, self.lesson, self.quiz, [q.pk])
        mastery_service.process_challenge_answer(_make_answer(s1, q, is_correct=False))
        # Bump mastery up high so mark_mistake_improved branches to mastered.
        SkillMastery.objects.filter(
            user=self.student, skill__code="greetings",
        ).update(mastery_score=95)
        # Now answer right.
        s2 = _make_session(self.student, self.lesson, self.quiz, [q.pk])
        mastery_service.process_challenge_answer(_make_answer(s2, q, is_correct=True))
        mistake = StudentMistake.objects.get(user=self.student, question=q)
        self.assertTrue(mistake.mastered)


# ---------------------------------------------------------------------------
# 5. Review scheduler
# ---------------------------------------------------------------------------

class ReviewSchedulerTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_learning_skills", verbosity=0)
        cls.course, cls.unit, cls.lesson, cls.quiz = _make_course("rev")
        cls.student = _make_user("rev-s1")
        CourseEnrollment.objects.get_or_create(user=cls.student, course=cls.course)

    def test_review_scheduled_after_wrong_answer(self):
        q = _make_question(self.quiz, metadata={"skill": "greetings"})
        s = _make_session(self.student, self.lesson, self.quiz, [q.pk])
        mastery_service.process_challenge_answer(_make_answer(s, q, is_correct=False))
        mistake = StudentMistake.objects.get(user=self.student, question=q)
        # First mistake: ~24h out.
        delta = mistake.next_review_at - timezone.now()
        self.assertGreater(delta.total_seconds(), 23 * 3600)
        self.assertLess(delta.total_seconds(), 25 * 3600)

    def test_review_window_tightens_on_repeats(self):
        q = _make_question(self.quiz, metadata={"skill": "greetings"})
        s1 = _make_session(self.student, self.lesson, self.quiz, [q.pk])
        mastery_service.process_challenge_answer(_make_answer(s1, q, is_correct=False))
        s2 = _make_session(self.student, self.lesson, self.quiz, [q.pk])
        mastery_service.process_challenge_answer(_make_answer(s2, q, is_correct=False))
        # review_count is now 1 → next_review_at ~12h out.
        mistake = StudentMistake.objects.get(user=self.student, question=q)
        delta = mistake.next_review_at - timezone.now()
        self.assertGreater(delta.total_seconds(), 11 * 3600)
        self.assertLess(delta.total_seconds(), 13 * 3600)
        # One more → review_count=2 → ~4h out.
        s3 = _make_session(self.student, self.lesson, self.quiz, [q.pk])
        mastery_service.process_challenge_answer(_make_answer(s3, q, is_correct=False))
        mistake.refresh_from_db()
        delta = mistake.next_review_at - timezone.now()
        self.assertGreater(delta.total_seconds(), 3 * 3600)
        self.assertLess(delta.total_seconds(), 5 * 3600)

    def test_due_mistakes_returned(self):
        q = _make_question(self.quiz, metadata={"skill": "greetings"})
        s = _make_session(self.student, self.lesson, self.quiz, [q.pk])
        mastery_service.process_challenge_answer(_make_answer(s, q, is_correct=False))
        # Force the mistake into the past.
        StudentMistake.objects.filter(user=self.student).update(
            next_review_at=timezone.now() - timedelta(hours=1),
        )
        due = review_scheduler.get_due_mistakes(self.student)
        self.assertEqual(len(due), 1)


# ---------------------------------------------------------------------------
# 6. Smart review queue
# ---------------------------------------------------------------------------

class SmartReviewQueueTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_learning_skills", verbosity=0)
        cls.course, cls.unit, cls.lesson, cls.quiz = _make_course("sm")
        cls.student = _make_user("sm-s1")
        CourseEnrollment.objects.get_or_create(user=cls.student, course=cls.course)

    def test_queue_prioritises_severity_then_oldest_due(self):
        q_low = _make_question(self.quiz, metadata={"skill": "greetings"},
                               question_type="tap_choice")      # low severity
        q_high = _make_question(self.quiz, metadata={"skill": "to_be_names"},
                                question_type="mistake_correction")  # high severity
        for q in (q_low, q_high):
            s = _make_session(self.student, self.lesson, self.quiz, [q.pk])
            mastery_service.process_challenge_answer(_make_answer(s, q, is_correct=False))
        # Pull both forward to the past so they're both due.
        StudentMistake.objects.filter(user=self.student).update(
            next_review_at=timezone.now() - timedelta(hours=1),
        )
        queue = smart_review_service.build_review_queue(self.student)
        self.assertEqual(len(queue), 2)
        # High severity should sort first when due_at is equal.
        self.assertEqual(queue[0]["mistake"].question_id, q_high.pk)


# ---------------------------------------------------------------------------
# 7. Recommendation engine — 5 branches
# ---------------------------------------------------------------------------

class RecommendationEngineTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_learning_skills", verbosity=0)
        cls.course, cls.unit, cls.lesson, cls.quiz = _make_course("rec")
        cls.student = _make_user("rec-s1")
        CourseEnrollment.objects.get_or_create(user=cls.student, course=cls.course)

    def test_recommend_due_review_first(self):
        q = _make_question(self.quiz, metadata={"skill": "greetings"})
        s = _make_session(self.student, self.lesson, self.quiz, [q.pk])
        mastery_service.process_challenge_answer(_make_answer(s, q, is_correct=False))
        StudentMistake.objects.filter(user=self.student).update(
            next_review_at=timezone.now() - timedelta(hours=1),
        )
        rec = phase6_recommendation.get_next_best_action(self.student)
        self.assertEqual(rec["kind"], "review_mistakes")

    def test_recommend_retry_after_failed_challenge(self):
        # A session ended as failed but no due mistakes.
        ChallengeSession.objects.create(
            user=self.student, lesson=self.lesson, quiz=self.quiz,
            status="failed", question_ids=[], total_questions=0,
            current_question_index=0,
            hearts_total=5, hearts_remaining=0,
        )
        rec = phase6_recommendation.get_next_best_action(self.student)
        self.assertEqual(rec["kind"], "retry_challenge")

    def test_recommend_weak_skill(self):
        skill = Skill.objects.get(code="greetings")
        SkillMastery.objects.create(
            user=self.student, skill=skill,
            mastery_score=20, attempts_count=3,
        )
        rec = phase6_recommendation.get_next_best_action(self.student)
        self.assertEqual(rec["kind"], "practice_skill")
        self.assertEqual(rec["payload"]["skill_code"], "greetings")

    def test_recommend_daily_goal_if_not_complete(self):
        # No mistakes, no failed session, no weak skill — fall to daily goal.
        rec = phase6_recommendation.get_next_best_action(self.student)
        self.assertEqual(rec["kind"], "daily_goal")

    def test_recommend_continue_if_no_issues(self):
        # Mark daily goal complete by injecting a row.
        from motivation.models import DailyGoalProgress
        DailyGoalProgress.objects.create(
            user=self.student, date=timezone.localdate(),
            xp_earned=100, completed=True, bonus_awarded=True,
        )
        rec = phase6_recommendation.get_next_best_action(self.student)
        self.assertEqual(rec["kind"], "continue_lesson")

    def test_get_weak_skills_orders_lowest_first(self):
        s1 = Skill.objects.get(code="greetings")
        s2 = Skill.objects.get(code="to_be_names")
        SkillMastery.objects.create(user=self.student, skill=s1,
                                    mastery_score=15, attempts_count=5)
        SkillMastery.objects.create(user=self.student, skill=s2,
                                    mastery_score=40, attempts_count=5)
        weak = phase6_recommendation.get_weak_skills(self.student, limit=2)
        self.assertEqual([w["skill"].code for w in weak], ["greetings", "to_be_names"])

    def test_mastery_summary_band_counts(self):
        s = Skill.objects.get(code="greetings")
        SkillMastery.objects.create(user=self.student, skill=s,
                                    mastery_score=75, confidence_level="strong",
                                    attempts_count=5)
        out = phase6_recommendation.get_mastery_summary(self.student)
        self.assertEqual(out["skills_practiced"], 1)
        self.assertEqual(out["by_confidence"]["strong"], 1)


# ---------------------------------------------------------------------------
# 8. Challenge engine integration + duplicate guard
# ---------------------------------------------------------------------------

class ChallengeIntegrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_learning_skills", verbosity=0)
        cls.course, cls.unit, cls.lesson, cls.quiz = _make_course("ci")
        for i in range(3):
            _make_question(
                cls.quiz, metadata={"skill": "greetings"},
                question_text=f"Pick #{i}",
                options=["Hello", "Banana"],
                correct_answer="Hello",
                question_type="multiple_choice",
                difficulty=0.5,
            )
        cls.student = _make_user("ci-s1")
        CourseEnrollment.objects.get_or_create(user=cls.student, course=cls.course)

    def test_challenge_answer_updates_mastery_and_mistake(self):
        from courses.services import challenge_runner
        session = challenge_runner.start_or_resume(self.student, self.lesson)
        q = LessonQuestion.objects.get(pk=session.question_ids[0])
        # Wrong answer.
        challenge_runner.submit_answer(session, q, "Banana")
        # Mastery updated.
        m = SkillMastery.objects.get(user=self.student, skill__code="greetings")
        self.assertEqual(m.attempts_count, 1)
        self.assertEqual(m.wrong_count, 1)
        # Mistake created.
        self.assertTrue(
            StudentMistake.objects.filter(user=self.student, question=q).exists()
        )

    def test_duplicate_submit_does_not_double_update_mastery(self):
        from courses.services import challenge_runner
        session = challenge_runner.start_or_resume(self.student, self.lesson)
        q = LessonQuestion.objects.get(pk=session.question_ids[0])
        challenge_runner.submit_answer(session, q, "Hello")
        # Second call — the runner returns the existing answer; mastery
        # was processed via the FIRST answer and the MasteryEvent guards
        # the second.
        challenge_runner.submit_answer(session, q, "Hello")
        m = SkillMastery.objects.get(user=self.student, skill__code="greetings")
        self.assertEqual(m.attempts_count, 1)

    def test_refresh_replay_does_not_duplicate_mastery(self):
        from courses.services import challenge_runner
        session = challenge_runner.start_or_resume(self.student, self.lesson)
        q = LessonQuestion.objects.get(pk=session.question_ids[0])
        challenge_runner.submit_answer(session, q, "Hello")
        a = ChallengeAnswer.objects.get(session=session, question=q)
        # Re-invoke mastery processor directly (e.g. simulating a manual job).
        mastery_service.process_challenge_answer(a)
        mastery_service.process_challenge_answer(a)
        self.assertEqual(MasteryEvent.objects.filter(challenge_answer=a).count(), 1)


# ---------------------------------------------------------------------------
# 9. Summary page surfaces learning context
# ---------------------------------------------------------------------------

class SummaryLearningContextTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_learning_skills", verbosity=0)
        cls.course, cls.unit, cls.lesson, cls.quiz = _make_course("sl")
        cls.q = _make_question(
            cls.quiz, metadata={"skill": "greetings"},
            options=["Hello"], correct_answer="Hello",
        )
        cls.student = _make_user("sl-s1")
        CourseEnrollment.objects.get_or_create(user=cls.student, course=cls.course)

    def test_summary_renders_skills_and_recommendation(self):
        from courses.services import challenge_runner
        from django.test import Client
        from django.urls import reverse
        session = challenge_runner.start_or_resume(self.student, self.lesson)
        q = LessonQuestion.objects.get(pk=session.question_ids[0])
        challenge_runner.submit_answer(session, q, "Hello")
        challenge_runner.continue_to_next(session)
        session.refresh_from_db()

        c = Client(SERVER_NAME="127.0.0.1")
        c.force_login(self.student)
        r = c.get(reverse("courses:challenge_summary",
                          args=[self.course.pk, self.lesson.pk, session.pk]),
                  HTTP_HOST="127.0.0.1")
        self.assertEqual(r.status_code, 200)
        body = r.content.decode()
        self.assertIn("data-skills-practiced", body)
        self.assertIn("data-recommendation", body)


# ---------------------------------------------------------------------------
# 10. Management command — backfill_question_skills
# ---------------------------------------------------------------------------

class BackfillSkillsCommandTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_learning_skills", verbosity=0)
        cls.course, cls.unit, cls.lesson, cls.quiz = _make_course("bf")
        cls.q = _make_question(cls.quiz, metadata={})

    def test_dry_run_does_not_write(self):
        call_command("backfill_question_skills", verbosity=0)
        self.q.refresh_from_db()
        self.assertNotIn("skills", self.q.metadata)

    def test_confirm_writes(self):
        call_command("backfill_question_skills", "--confirm", verbosity=0)
        self.q.refresh_from_db()
        self.assertEqual(self.q.metadata.get("skills"), ["to_be_names"])
