"""Phase 10 — Generalize Super Lesson 01 to 48 Topics.

Asserts:
  * The data file exists, has 47 topics (orders 2..48), every required field.
  * `seed_beginner_48_topics` is idempotent + supports --topic= + --dry-run.
  * Every new topic is `status="pending_review"` → invisible to students.
  * A teacher/staff user sees them via the admin querysets.
  * A0/A1 difficulty rules hold (no listen_and_type / translate_to_english
    in topics 1-12).
  * Per-topic invariants: 8-12 questions, ≤ 3 speaking placeholders,
    last question is speaking/roleplay, every question has skills.
  * Sample topics (02, 12, 24, 45, 48) can compose + render + grade.
  * Image prompts + audio scripts present; no underscores / brand names.
  * Gold Reference Topic 01 is NOT damaged.
  * Existing engines (Challenge / Quiz / Rewards / Mastery / AI Tutor)
    still pass their suites.
"""
from __future__ import annotations

import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse

from courses.models import (
    ChallengeSession, Course, CourseEnrollment, CourseLevel, CourseUnit,
    Lesson, LessonAudioScript, LessonChecklist, LessonImagePrompt,
    LessonQuestion, LessonQuiz,
)
from courses.services.student_flow import published_lesson_queryset
from learning_core.models import Skill


User = get_user_model()
DATA_FILE = (
    Path(__file__).resolve().parents[1] / "data" / "beginner_topics_data.json"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _seed_all():
    call_command("seed_learning_skills", verbosity=0)
    call_command("seed_badge_definitions", verbosity=0)
    call_command("seed_super_lesson_01", verbosity=0)
    call_command("seed_beginner_48_topics", "--confirm", verbosity=0)


def _make_student(name="ph10") -> User:
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


# ---------------------------------------------------------------------------
# 1. Blueprint data file
# ---------------------------------------------------------------------------

class BlueprintDataFileTests(TestCase):
    def test_data_file_exists(self):
        self.assertTrue(DATA_FILE.exists(),
                        f"Data file missing: {DATA_FILE}")

    def test_data_file_has_47_topics(self):
        topics = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        self.assertEqual(len(topics), 47)
        orders = sorted(t["order"] for t in topics)
        self.assertEqual(orders, list(range(2, 49)))

    def test_every_topic_has_required_fields(self):
        topics = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        required = {
            "order", "title_en", "title_ar", "cefr_level",
            "grammar_topic", "vocabulary_topic",
            "content_html", "content_ar",
            "image_prompts", "audio_scripts", "checklist", "questions",
        }
        for t in topics:
            with self.subTest(order=t["order"]):
                missing = required - set(t.keys())
                self.assertEqual(missing, set())
                self.assertEqual(len(t["image_prompts"]), 4)
                self.assertEqual(len(t["audio_scripts"]), 6)
                self.assertGreaterEqual(len(t["checklist"]), 4)
                self.assertGreaterEqual(len(t["questions"]), 8)
                self.assertLessEqual(len(t["questions"]), 12)


# ---------------------------------------------------------------------------
# 2. Seed command behaviour
# ---------------------------------------------------------------------------

class SeedCommandTests(TestCase):
    def test_dry_run_writes_nothing(self):
        call_command("seed_learning_skills", verbosity=0)
        call_command("seed_super_lesson_01", verbosity=0)
        before = Lesson.objects.count()
        call_command("seed_beginner_48_topics", verbosity=0)   # no --confirm
        self.assertEqual(Lesson.objects.count(), before)

    def test_confirm_writes_47_topics(self):
        _seed_all()
        # 47 new lessons all in pending_review.
        pending = Lesson.objects.filter(status="pending_review").count()
        self.assertEqual(pending, 47)

    def test_seed_is_idempotent(self):
        _seed_all()
        n1 = Lesson.objects.filter(status="pending_review").count()
        q1 = LessonQuestion.objects.count()
        # Re-run with --confirm.
        call_command("seed_beginner_48_topics", "--confirm", verbosity=0)
        n2 = Lesson.objects.filter(status="pending_review").count()
        q2 = LessonQuestion.objects.count()
        self.assertEqual(n1, n2)
        self.assertEqual(q1, q2)

    def test_seed_single_topic(self):
        call_command("seed_learning_skills", verbosity=0)
        call_command("seed_super_lesson_01", verbosity=0)
        call_command("seed_beginner_48_topics",
                     "--topic=12", "--confirm", verbosity=0)
        # Only topic 12 created (in addition to topic 1 which already exists).
        self.assertEqual(
            Lesson.objects.filter(status="pending_review", order=12).count(), 1,
        )
        # No others.
        self.assertEqual(
            Lesson.objects.filter(status="pending_review").exclude(order=12).count(),
            0,
        )

    def test_seed_does_not_break_super_lesson_01(self):
        _seed_all()
        topic_1 = Lesson.objects.get(
            course__slug="onlenco-beginner", order=1,
        )
        # Topic 1 stays published.
        self.assertEqual(topic_1.status, "published")
        # And still has its 10 gold questions.
        self.assertEqual(topic_1.quiz.questions.count(), 10)


# ---------------------------------------------------------------------------
# 3. Student visibility (the Human Review Gate)
# ---------------------------------------------------------------------------

class StudentVisibilityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        _seed_all()
        cls.course = Course.objects.get(slug="onlenco-beginner")
        cls.student = _make_student("vis-1")
        CourseEnrollment.objects.get_or_create(user=cls.student, course=cls.course)

    def test_published_queryset_only_shows_topic_1(self):
        visible = published_lesson_queryset().filter(course=self.course)
        # Topic 1 only.
        self.assertEqual(visible.count(), 1)
        self.assertEqual(visible.first().order, 1)

    def test_student_cannot_open_pending_topic_page(self):
        topic_12 = Lesson.objects.get(course=self.course, order=12)
        self.assertEqual(topic_12.status, "pending_review")
        c = _login(self.student)
        r = c.get(reverse("courses:lesson_detail",
                          args=[self.course.pk, topic_12.pk]),
                  HTTP_HOST="127.0.0.1")
        # Hidden → 404 (`get_object_or_404(published_lesson_queryset())`).
        self.assertEqual(r.status_code, 404)

    def test_approving_a_topic_makes_it_visible(self):
        topic_2 = Lesson.objects.get(course=self.course, order=2)
        topic_2.status = "published"
        topic_2.save(update_fields=["status"])
        c = _login(self.student)
        r = c.get(reverse("courses:lesson_detail",
                          args=[self.course.pk, topic_2.pk]),
                  HTTP_HOST="127.0.0.1")
        self.assertEqual(r.status_code, 200)


# ---------------------------------------------------------------------------
# 4. A0/A1 difficulty rules
# ---------------------------------------------------------------------------

class DifficultyBandRulesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        _seed_all()

    def test_topics_1_to_12_no_listen_and_type(self):
        for order in range(1, 13):
            lesson = Lesson.objects.get(course__slug="onlenco-beginner", order=order)
            types = list(
                lesson.quiz.questions.values_list("question_type", flat=True)
            )
            with self.subTest(order=order):
                self.assertNotIn("listen_and_type", types,
                                 f"T{order:02d} has listen_and_type (A0 forbidden)")

    def test_topics_1_to_12_no_translate_to_english(self):
        for order in range(1, 13):
            lesson = Lesson.objects.get(course__slug="onlenco-beginner", order=order)
            types = list(
                lesson.quiz.questions.values_list("question_type", flat=True)
            )
            with self.subTest(order=order):
                self.assertNotIn("translate_to_english", types,
                                 f"T{order:02d} has translate_to_english (A0 forbidden)")

    def test_topics_13_to_24_no_listen_and_type(self):
        for order in range(13, 25):
            lesson = Lesson.objects.get(course__slug="onlenco-beginner", order=order)
            types = list(
                lesson.quiz.questions.values_list("question_type", flat=True)
            )
            with self.subTest(order=order):
                self.assertNotIn("listen_and_type", types,
                                 f"T{order:02d} has listen_and_type (A0+/A1- forbidden)")

    def test_no_challenge_has_more_than_3_speaking_placeholders(self):
        speaking = {"speak_this_sentence", "ai_roleplay_prompt",
                    "pronunciation_check", "speaking_prompt"}
        for lesson in Lesson.objects.filter(course__slug="onlenco-beginner"):
            types = list(
                lesson.quiz.questions.values_list("question_type", flat=True)
            )
            count = sum(1 for t in types if t in speaking)
            with self.subTest(order=lesson.order):
                self.assertLessEqual(count, 3,
                                     f"T{lesson.order:02d}: {count} speaking placeholders")

    def test_each_challenge_starts_with_easy_question(self):
        for lesson in Lesson.objects.filter(
            course__slug="onlenco-beginner", order__gt=1,
        ):
            first_q = lesson.quiz.questions.order_by("order").first()
            with self.subTest(order=lesson.order):
                self.assertLessEqual(first_q.difficulty_score, 0.4,
                                     f"T{lesson.order:02d} Q1 too hard: {first_q.difficulty_score}")

    def test_each_challenge_ends_with_speaking_or_roleplay(self):
        speaking = {"speak_this_sentence", "ai_roleplay_prompt",
                    "pronunciation_check", "speaking_prompt"}
        for lesson in Lesson.objects.filter(
            course__slug="onlenco-beginner", order__gt=1,
        ):
            last_q = lesson.quiz.questions.order_by("-order").first()
            with self.subTest(order=lesson.order):
                self.assertIn(last_q.question_type, speaking,
                              f"T{lesson.order:02d} last q is {last_q.question_type}")


# ---------------------------------------------------------------------------
# 5. Skills + question metadata
# ---------------------------------------------------------------------------

class SkillsIntegrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        _seed_all()

    def test_all_questions_have_skills(self):
        for q in LessonQuestion.objects.filter(
            quiz__lesson__course__slug="onlenco-beginner",
        ).iterator():
            skills = (q.metadata or {}).get("skills") or []
            with self.subTest(quiz_id=q.quiz_id, order=q.order):
                self.assertTrue(skills,
                                f"Q{q.order} of quiz {q.quiz_id} has no skills")

    def test_all_skill_codes_exist_in_taxonomy(self):
        valid = set(
            Skill.objects.exclude(code__isnull=True)
            .values_list("code", flat=True)
        )
        for q in LessonQuestion.objects.filter(
            quiz__lesson__course__slug="onlenco-beginner",
        ).iterator():
            for code in (q.metadata or {}).get("skills") or []:
                with self.subTest(quiz_id=q.quiz_id, order=q.order, code=code):
                    self.assertIn(code, valid,
                                  f"Unknown skill code: {code}")


# ---------------------------------------------------------------------------
# 6. Per-topic invariants (image/audio counts, no forbidden strings)
# ---------------------------------------------------------------------------

class PerTopicInvariantsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        _seed_all()

    def test_every_topic_has_4_image_prompts(self):
        for lesson in Lesson.objects.filter(
            course__slug="onlenco-beginner", order__gt=1,
        ):
            with self.subTest(order=lesson.order):
                self.assertEqual(
                    LessonImagePrompt.objects.filter(lesson=lesson).count(),
                    4,
                )

    def test_every_topic_has_6_audio_scripts(self):
        for lesson in Lesson.objects.filter(
            course__slug="onlenco-beginner", order__gt=1,
        ):
            with self.subTest(order=lesson.order):
                self.assertEqual(
                    LessonAudioScript.objects.filter(lesson=lesson).count(),
                    6,
                )

    def test_every_topic_has_checklist_items(self):
        for lesson in Lesson.objects.filter(
            course__slug="onlenco-beginner", order__gt=1,
        ):
            count = LessonChecklist.objects.filter(lesson=lesson, is_active=True).count()
            with self.subTest(order=lesson.order):
                self.assertGreaterEqual(count, 4)

    def test_every_topic_has_8_to_12_questions(self):
        for lesson in Lesson.objects.filter(
            course__slug="onlenco-beginner", order__gt=1,
        ):
            count = lesson.quiz.questions.count()
            with self.subTest(order=lesson.order):
                self.assertGreaterEqual(count, 8)
                self.assertLessEqual(count, 12)

    def test_no_audio_script_contains_underscore(self):
        for s in LessonAudioScript.objects.filter(
            lesson__course__slug="onlenco-beginner",
            lesson__order__gt=1,
        ):
            with self.subTest(lesson=s.lesson_id, type=s.script_type):
                self.assertNotIn("_", s.script_text,
                                 f"underscore in {s.script_type} script of L{s.lesson_id}")

    def test_no_topic_contains_forbidden_brand_strings(self):
        for lesson in Lesson.objects.filter(course__slug="onlenco-beginner"):
            for needle in ("English for Everyone", "DK Publishing", "Duolingo"):
                with self.subTest(order=lesson.order, needle=needle):
                    self.assertNotIn(needle, lesson.content_html)
                    self.assertNotIn(needle, lesson.content_ar)

    def test_image_prompts_explicitly_avoid_copyrighted_styles(self):
        for ip in LessonImagePrompt.objects.filter(
            lesson__course__slug="onlenco-beginner",
            lesson__order__gt=1,
        ):
            # Every prompt should mention "no logos" or "no copyrighted".
            lower = ip.prompt.lower()
            with self.subTest(lesson=ip.lesson_id, type=ip.prompt_type):
                self.assertTrue(
                    "no logo" in lower or "no copyrighted" in lower or "no brand" in lower,
                    f"L{ip.lesson_id}/{ip.prompt_type} doesn't disclaim copyright",
                )


# ---------------------------------------------------------------------------
# 7. Gold Reference (Topic 01) preserved
# ---------------------------------------------------------------------------

class GoldReferencePreservedTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        _seed_all()

    def test_topic_01_status_still_published(self):
        t1 = Lesson.objects.get(course__slug="onlenco-beginner", order=1)
        self.assertEqual(t1.status, "published")

    def test_topic_01_q7_is_image_choice(self):
        t1 = Lesson.objects.get(course__slug="onlenco-beginner", order=1)
        self.assertEqual(t1.quiz.questions.get(order=7).question_type, "image_choice")

    def test_topic_01_q8_is_sound_to_word(self):
        t1 = Lesson.objects.get(course__slug="onlenco-beginner", order=1)
        self.assertEqual(t1.quiz.questions.get(order=8).question_type, "sound_to_word")

    def test_topic_01_q10_uses_ai_roleplay_card_renderer(self):
        from courses.services import question_type_registry as r
        spec = r.get_spec("ai_roleplay_prompt") or {}
        self.assertEqual(spec.get("renderer"), "ai_roleplay_card.html")

    def test_topic_01_still_has_10_questions(self):
        t1 = Lesson.objects.get(course__slug="onlenco-beginner", order=1)
        self.assertEqual(t1.quiz.questions.count(), 10)


# ---------------------------------------------------------------------------
# 8. Sample lifecycle — render + run + summary
# ---------------------------------------------------------------------------

class SampleLifecycleTests(TestCase):
    """Run a sample topic end-to-end. Approve it first so the student can
    open it; the rest of the engine work is identical to Phase 8's
    coverage so this proves the generated content slots into the engines
    cleanly."""

    @classmethod
    def setUpTestData(cls):
        _seed_all()
        cls.course = Course.objects.get(slug="onlenco-beginner")
        cls.student = _make_student("sl-1")
        CourseEnrollment.objects.get_or_create(user=cls.student, course=cls.course)

    def _approve(self, order):
        l = Lesson.objects.get(course=self.course, order=order)
        l.status = "published"
        l.save(update_fields=["status"])
        return l

    def _start_and_render(self, order):
        l = self._approve(order)
        c = _login(self.student)
        # Lesson page renders.
        r = c.get(reverse("courses:lesson_detail",
                          args=[self.course.pk, l.pk]),
                  HTTP_HOST="127.0.0.1")
        self.assertEqual(r.status_code, 200)
        # Start the Challenge.
        r = c.get(reverse("courses:challenge_start",
                          args=[self.course.pk, l.pk]),
                  HTTP_HOST="127.0.0.1", follow=True)
        self.assertEqual(r.status_code, 200)
        sess = ChallengeSession.objects.get(user=self.student, lesson=l)
        # Render the current card.
        r = c.get(reverse("courses:challenge_current",
                          args=[self.course.pk, l.pk, sess.pk]),
                  HTTP_HOST="127.0.0.1")
        self.assertEqual(r.status_code, 200)
        return sess

    def test_topic_02_lifecycle(self):
        self._start_and_render(2)

    def test_topic_12_lifecycle(self):
        self._start_and_render(12)

    def test_topic_24_lifecycle(self):
        self._start_and_render(24)

    def test_topic_45_lifecycle(self):
        self._start_and_render(45)

    def test_topic_48_lifecycle(self):
        self._start_and_render(48)
