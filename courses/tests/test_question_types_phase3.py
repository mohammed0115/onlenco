"""Phase 3 — Question Types: registry, graders, renderers, integration.

Covers:
  * Registry schema completeness + parity between registry keys and the
    grader dispatcher.
  * Per-type graders for every gradable type (positive + negative paths).
  * Renderer partial existence + safe template rendering of the demo
    lesson via the Challenge view.
  * Mixed-challenge integration end-to-end on a fully-seeded demo
    lesson (one of each type).
  * Backward compatibility with the legacy Classic Quiz types still
    handled by `quiz_grader`.
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.template.loader import get_template
from django.test import Client, TestCase
from django.urls import reverse

from courses.models import (
    ChallengeAnswer, ChallengeSession, Course, CourseEnrollment,
    CourseLevel, CourseUnit, Lesson, LessonQuestion, LessonQuiz,
)
from courses.services import (
    challenge_composer, challenge_grading,
    question_graders, question_type_registry as registry,
)


User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_course(slug: str, *, level_code: str = "C0") -> tuple[Course, CourseUnit]:
    level, _ = CourseLevel.objects.get_or_create(
        code=level_code,
        defaults={"name": f"Phase3 tests {level_code}", "order": 99},
    )
    teacher = User.objects.create_user(
        username=f"teacher-{slug}", password="pw",
        email=f"teacher-{slug}@onlenco.test",
    )
    course = Course.objects.create(
        title=f"Phase3 {slug}", slug=slug, level=level,
        teacher=teacher, created_by=teacher,
        status="published", is_active=True,
    )
    unit = CourseUnit.objects.create(course=course, title="U1", order=1)
    return course, unit


def _make_lesson_with_questions(course, unit, defs: list[dict]) -> tuple[Lesson, LessonQuiz]:
    lesson = Lesson.objects.create(
        course=course, unit=unit, title="L1", order=1,
        status="published", is_active=True,
    )
    quiz = LessonQuiz.objects.create(lesson=lesson, title="Q1")
    for i, d in enumerate(defs):
        LessonQuestion.objects.create(
            quiz=quiz, order=i + 1,
            question_type=d["question_type"],
            question_text=d.get("question_text", "Q"),
            options=d.get("options", []) or [],
            metadata=d.get("metadata", {}),
            correct_answer=d.get("correct_answer", ""),
        )
    return lesson, quiz


def _make_student(name: str) -> User:
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


# ---------------------------------------------------------------------------
# 1. Registry shape + invariants
# ---------------------------------------------------------------------------

class RegistrySchemaTests(TestCase):
    REQUIRED_KEYS = {
        "label_en", "label_ar", "skill", "requires_metadata",
        "required_metadata_keys", "supports_auto_grading",
        "supports_challenge", "renderer", "grader", "placeholder",
    }

    def test_every_entry_has_required_keys(self):
        for code, spec in registry.ALL_TYPES.items():
            with self.subTest(code=code):
                missing = self.REQUIRED_KEYS - set(spec.keys())
                self.assertEqual(missing, set(),
                                 f"{code} missing required keys: {missing}")

    def test_launch_set_has_20_entries(self):
        # The new 20 launch types — must all be present.
        self.assertEqual(len(registry.QUESTION_TYPE_REGISTRY), 20)

    def test_every_renderer_template_exists(self):
        for code, spec in registry.ALL_TYPES.items():
            path = "courses/question_renderers/" + spec["renderer"]
            with self.subTest(code=code, path=path):
                # Raises TemplateDoesNotExist if missing.
                get_template(path)

    def test_every_grader_key_maps_to_a_function(self):
        for code, spec in registry.ALL_TYPES.items():
            with self.subTest(code=code):
                self.assertIn(
                    spec["grader"], question_graders.GRADERS,
                    f"{code} → grader '{spec['grader']}' is not in GRADERS",
                )

    def test_skill_values_are_known(self):
        allowed = {"vocabulary", "grammar", "listening",
                   "speaking", "reading", "writing"}
        for code, spec in registry.ALL_TYPES.items():
            with self.subTest(code=code):
                self.assertTrue(spec["skill"], f"{code} has empty skill list")
                self.assertTrue(set(spec["skill"]) <= allowed,
                                f"{code} has unknown skill: {spec['skill']}")

    def test_unknown_type_falls_back_safely(self):
        self.assertFalse(registry.is_known("totally_made_up"))
        self.assertEqual(registry.renderer_for("totally_made_up"),
                         "unsupported_question.html")
        self.assertEqual(registry.grader_key("totally_made_up"), "")

    def test_validate_metadata_flags_missing_keys(self):
        missing = registry.validate_metadata("tap_choice", {})
        self.assertIn("options", missing)
        self.assertIn("correct_option_id", missing)
        ok = registry.validate_metadata(
            "tap_choice", {"options": [], "correct_option_id": "a"},
        )
        self.assertEqual(ok, [])

    def test_label_lookup_prefers_lang(self):
        self.assertEqual(registry.label("tap_choice", lang="en"),
                         "Pick the right answer")
        self.assertEqual(registry.label("tap_choice", lang="ar"),
                         "اختر الإجابة الصحيحة")

    def test_composer_supported_set_matches_registry(self):
        expected = {c for c, s in registry.ALL_TYPES.items()
                    if s.get("supports_challenge")}
        self.assertEqual(challenge_composer.SUPPORTED_QUESTION_TYPES, expected)


# ---------------------------------------------------------------------------
# 2. Per-type graders — positive + negative
# ---------------------------------------------------------------------------

def _mk(question_type, *, metadata=None, correct_answer=""):
    """Make a transient LessonQuestion-shaped object for grader tests."""
    class _Q:
        pass
    q = _Q()
    q.question_type = question_type
    q.metadata = metadata or {}
    q.correct_answer = correct_answer
    return q


class GraderTests(TestCase):
    # --- tap_choice ---
    def test_tap_choice_correct(self):
        q = _mk("tap_choice", metadata={
            "options": [{"id": "a", "text": "Yes"}, {"id": "b", "text": "No"}],
            "correct_option_id": "a",
        }, correct_answer="a")
        res = challenge_grading.grade(q, "a")
        self.assertTrue(res["is_correct"])

    def test_tap_choice_wrong(self):
        q = _mk("tap_choice", metadata={
            "options": [{"id": "a", "text": "Yes"}],
            "correct_option_id": "a",
        }, correct_answer="a")
        res = challenge_grading.grade(q, "b")
        self.assertFalse(res["is_correct"])

    # --- listen_and_type ---
    def test_listen_and_type_forgiving(self):
        q = _mk("listen_and_type", metadata={
            "audio_script": "Hi", "correct_answer": "I drink coffee every morning.",
        }, correct_answer="I drink coffee every morning.")
        # punctuation + case shouldn't matter
        res = challenge_grading.grade(q, "i drink coffee every morning")
        self.assertTrue(res["is_correct"])

    def test_listen_and_type_wrong(self):
        q = _mk("listen_and_type", metadata={
            "correct_answer": "I drink tea every morning.",
        })
        res = challenge_grading.grade(q, "I drink water")
        self.assertFalse(res["is_correct"])

    # --- picture_labeling / translate_to_english — accepted_answers ---
    def test_accepted_answers_first_variant(self):
        q = _mk("picture_labeling", metadata={
            "accepted_answers": ["water", "a glass of water"],
        })
        self.assertTrue(challenge_grading.grade(q, "Water")["is_correct"])

    def test_accepted_answers_second_variant(self):
        q = _mk("picture_labeling", metadata={
            "accepted_answers": ["water", "a glass of water"],
        })
        self.assertTrue(challenge_grading.grade(q, "A glass of water.")["is_correct"])

    def test_accepted_answers_rejects_random(self):
        q = _mk("translate_to_english", metadata={
            "accepted_answers": ["Noor works at a small clinic."],
        })
        self.assertFalse(challenge_grading.grade(q, "Noor is happy")["is_correct"])

    # --- word_bank_sentence ---
    def test_word_bank_correct_json(self):
        q = _mk("word_bank_sentence", metadata={
            "word_bank": ["A", "B"],
            "correct_order": ["A", "B"],
        })
        res = challenge_grading.grade(q, '["A","B"]')
        self.assertTrue(res["is_correct"])

    def test_word_bank_correct_pipe(self):
        q = _mk("word_bank_sentence", metadata={
            "correct_order": ["My", "name", "is", "Amani"],
        })
        res = challenge_grading.grade(q, "My name is Amani")
        self.assertTrue(res["is_correct"])

    def test_word_bank_wrong_order(self):
        q = _mk("word_bank_sentence", metadata={
            "correct_order": ["A", "B", "C"],
        })
        res = challenge_grading.grade(q, '["C","B","A"]')
        self.assertFalse(res["is_correct"])

    # --- match_pairs ---
    def test_match_pairs_partial_credit(self):
        q = _mk("match_pairs", metadata={
            "pairs": [
                {"left": "Noor", "right": "nurse"},
                {"left": "Tarek", "right": "driver"},
                {"left": "Hala", "right": "engineer"},
                {"left": "Rashid", "right": "baker"},
            ],
        })
        # 2/4 correct
        res = challenge_grading.grade(q, '{"Noor":"nurse","Tarek":"driver","Hala":"baker","Rashid":"engineer"}')
        self.assertFalse(res["is_correct"])
        self.assertEqual(res["score"], 0.5)

    def test_match_pairs_perfect(self):
        q = _mk("match_pairs", metadata={
            "pairs": [
                {"left": "A", "right": "1"},
                {"left": "B", "right": "2"},
            ],
        })
        res = challenge_grading.grade(q, '{"A":"1","B":"2"}')
        self.assertTrue(res["is_correct"])

    # --- fill_blank_card / normalize_equality ---
    def test_fill_blank_card_correct(self):
        q = _mk("fill_blank_card", correct_answer="is")
        self.assertTrue(challenge_grading.grade(q, "is.")["is_correct"])

    # --- frequency_scale (single-target) ---
    def test_frequency_scale_within_tolerance(self):
        q = _mk("frequency_scale", metadata={
            "target": {"label": "often", "percent": 65}, "tolerance": 10,
        })
        self.assertTrue(challenge_grading.grade(q, "70")["is_correct"])

    def test_frequency_scale_outside_tolerance(self):
        q = _mk("frequency_scale", metadata={
            "target": {"label": "often", "percent": 65}, "tolerance": 10,
        })
        self.assertFalse(challenge_grading.grade(q, "5")["is_correct"])

    # --- mistake_correction ---
    def test_mistake_correction_accepts_variant(self):
        q = _mk("mistake_correction", metadata={
            "corrected_sentence": "Salma doesn't like apples.",
            "accepted_answers": ["Salma does not like apples."],
        })
        self.assertTrue(challenge_grading.grade(q, "Salma does not like apples")["is_correct"])

    # --- placeholders (speak / pronunciation / roleplay) — always ok ---
    def test_speak_this_sentence_is_self_check(self):
        q = _mk("speak_this_sentence", metadata={"sentence": "Hello"})
        res = challenge_grading.grade(q, "self_read")
        self.assertTrue(res["is_correct"])
        self.assertEqual(res["score"], 1.0)

    def test_pronunciation_check_is_self_check(self):
        q = _mk("pronunciation_check", metadata={"target_word": "thirteen"})
        self.assertTrue(challenge_grading.grade(q, "self_read")["is_correct"])

    def test_ai_roleplay_is_self_check(self):
        q = _mk("ai_roleplay_prompt", metadata={"scenario": "x"})
        self.assertTrue(challenge_grading.grade(q, "self_read")["is_correct"])

    # --- unknown type ---
    def test_unknown_type_returns_unsupported(self):
        q = _mk("nope_not_a_real_type")
        res = challenge_grading.grade(q, "anything")
        self.assertFalse(res["is_correct"])
        self.assertTrue(res.get("_unsupported"))


# ---------------------------------------------------------------------------
# 3. Composer integration — mixed types
# ---------------------------------------------------------------------------

class ComposerWithNewTypesTests(TestCase):
    def test_composer_includes_new_types(self):
        course, unit = _make_course("cmp-new")
        lesson, quiz = _make_lesson_with_questions(course, unit, [
            {"question_type": "tap_choice",
             "metadata": {"options": [{"id": "a", "text": "Yes"}], "correct_option_id": "a"},
             "correct_answer": "a"},
            {"question_type": "match_pairs",
             "metadata": {"pairs": [{"left": "A", "right": "1"}]},
             "correct_answer": ""},
            {"question_type": "ai_roleplay_prompt",
             "metadata": {"scenario": "x"}, "correct_answer": ""},
        ])
        qids = challenge_composer.compose_question_ids(quiz)
        self.assertEqual(len(qids), 3)

    def test_composer_drops_writing_prompt(self):
        # writing_prompt is supports_challenge=False — must be skipped.
        course, unit = _make_course("cmp-skip")
        lesson, quiz = _make_lesson_with_questions(course, unit, [
            {"question_type": "tap_choice",
             "metadata": {"options": [{"id": "a", "text": "Yes"}], "correct_option_id": "a"},
             "correct_answer": "a"},
            {"question_type": "writing_prompt", "correct_answer": ""},
        ])
        qids = challenge_composer.compose_question_ids(quiz)
        self.assertEqual(len(qids), 1)


# ---------------------------------------------------------------------------
# 4. End-to-end Challenge session over the seeded demo lesson
# ---------------------------------------------------------------------------

class DemoLessonIntegrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Run the seeder — it builds the full 20-type demo lesson.
        call_command("seed_course_levels", verbosity=0)
        call_command("seed_challenge_question_types_demo", verbosity=0)
        cls.lesson = Lesson.objects.get(title="Challenge Types Showcase")
        cls.course = cls.lesson.course
        cls.student = _make_student("demo-1")
        CourseEnrollment.objects.get_or_create(user=cls.student, course=cls.course)

    def test_demo_lesson_has_twenty_questions(self):
        self.assertEqual(self.lesson.quiz.questions.count(), 20)

    def test_demo_lesson_every_question_renders_in_challenge(self):
        """Each of the 20 demo questions renders without crashing.

        Builds a fresh ChallengeSession for every question (rather than
        walking the session forward — which would deplete hearts on
        wrong answers and end the session early). The aim is renderer
        coverage, not lifecycle coverage (the lifecycle is covered in
        test_challenge_engine.py).
        """
        c = _login(self.student)
        questions = list(self.lesson.quiz.questions.all().order_by("order"))
        self.assertEqual(len(questions), 20)
        for q in questions:
            with self.subTest(question_type=q.question_type):
                # Reset any active session and pin one to this question.
                ChallengeSession.objects.filter(
                    user=self.student, lesson=self.lesson,
                ).delete()
                session = ChallengeSession.objects.create(
                    user=self.student, lesson=self.lesson,
                    quiz=self.lesson.quiz, status="in_progress",
                    question_ids=[q.pk], total_questions=1,
                    current_question_index=0,
                    hearts_total=5, hearts_remaining=5,
                )
                r = c.get(reverse("courses:challenge_current",
                                  args=[self.course.pk, self.lesson.pk, session.pk]),
                          HTTP_HOST="127.0.0.1")
                self.assertEqual(r.status_code, 200,
                                 f"{q.question_type} failed to render")
                body = r.content.decode("utf-8", errors="ignore")
                self.assertIn("onlenco-ch-question__text", body)
                self.assertIn("onlenco-qr", body)

    def test_demo_lesson_composer_yields_capped_set(self):
        qids = challenge_composer.compose_question_ids(self.lesson.quiz)
        # Composer cap is 12 — must be no more than that.
        self.assertLessEqual(len(qids), challenge_composer.MAX_CARDS)
        self.assertGreater(len(qids), 0)


# ---------------------------------------------------------------------------
# 5. Backward compatibility — legacy types still work
# ---------------------------------------------------------------------------

class LegacyBackcompatTests(TestCase):
    def test_legacy_multiple_choice_still_grades(self):
        q = _mk("multiple_choice", correct_answer="Hello")
        self.assertTrue(challenge_grading.grade(q, "hello")["is_correct"])
        self.assertFalse(challenge_grading.grade(q, "Banana")["is_correct"])

    def test_legacy_fill_blank_still_grades(self):
        q = _mk("fill_blank", correct_answer="is")
        self.assertTrue(challenge_grading.grade(q, "is")["is_correct"])

    def test_legacy_correction_still_grades(self):
        q = _mk("correction", correct_answer="She is happy.")
        self.assertTrue(challenge_grading.grade(q, "she is happy")["is_correct"])

    def test_legacy_speaking_prompt_is_self_check(self):
        q = _mk("speaking_prompt")
        self.assertTrue(challenge_grading.grade(q, "self_read")["is_correct"])

    def test_legacy_writing_prompt_excluded_from_challenge(self):
        self.assertFalse(registry.supports_challenge("writing_prompt"))
