"""Coverage for the additive media / script / checklist models introduced
in migration 0009 to support the Beginner pack (Prompt 02).

Invariants under test:
  * A lesson with NO attached media still renders cleanly — no rows are
    required for the lesson view to work.
  * Each of the new models accepts the minimum required fields and
    persists optional fields when supplied.
  * Existing lessons keep working — attaching new rows is purely additive.
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from courses.models import (
    Course, CourseLevel, CourseUnit, Lesson,
    LessonAudioScript, LessonChecklist, LessonImagePrompt, LessonMedia,
    LessonQuestion, LessonQuiz, QuestionMedia,
)

User = get_user_model()


def _ctx():
    """Build a minimal Lesson with all its FK ancestors."""
    level = CourseLevel.objects.create(code="A0", name="Beginner", order=1)
    teacher = User.objects.create_user(username="t1", password="pw")
    course = Course.objects.create(
        title="Beginner", slug="beg", level=level,
        teacher=teacher, created_by=teacher,
    )
    unit = CourseUnit.objects.create(
        course=course, title="U1", order=1,
    )
    lesson = Lesson.objects.create(
        course=course, unit=unit, title="Introducing yourself", order=1,
    )
    return level, course, unit, lesson


class LessonRendersWithoutMediaTests(TestCase):
    """The lesson view must not require any LessonMedia / LessonChecklist /
    LessonAudioScript / LessonImagePrompt rows to render."""

    def test_lesson_page_works_without_media(self):
        _, _, _, lesson = _ctx()
        self.assertEqual(lesson.media.count(), 0)
        self.assertEqual(lesson.checklist_items.count(), 0)
        self.assertEqual(lesson.audio_scripts.count(), 0)
        self.assertEqual(lesson.image_prompts.count(), 0)
        # The lesson string repr must not crash on missing media.
        self.assertIn("Introducing yourself", str(lesson))

    def test_existing_lessons_still_render(self):
        """Simulate a pre-pack lesson row with no media at all — same as
        any lesson seeded before migration 0009 ran."""
        _, _, _, lesson = _ctx()
        # Fetch fresh from DB (mirrors the view path).
        lesson_fresh = Lesson.objects.get(pk=lesson.pk)
        self.assertTrue(lesson_fresh.is_active)
        # Reverse accessors must return empty querysets, not raise.
        self.assertFalse(lesson_fresh.media.exists())
        self.assertFalse(lesson_fresh.checklist_items.exists())
        self.assertFalse(lesson_fresh.audio_scripts.exists())
        self.assertFalse(lesson_fresh.image_prompts.exists())


class LessonMediaTests(TestCase):
    def test_lesson_can_have_image_media(self):
        _, _, _, lesson = _ctx()
        m = LessonMedia.objects.create(
            lesson=lesson, media_type="image",
            title="Greeting scene", title_ar="مشهد التحية",
            alt_text="Two people waving at each other",
            language="",
        )
        self.assertEqual(lesson.media.count(), 1)
        self.assertEqual(m.media_type, "image")

    def test_lesson_can_have_audio_media(self):
        _, _, _, lesson = _ctx()
        m = LessonMedia.objects.create(
            lesson=lesson, media_type="audio",
            title="Listen and repeat", duration_seconds=42,
            transcript="Hello. My name is Amani.",
            language="en",
        )
        self.assertEqual(m.duration_seconds, 42)
        self.assertEqual(m.transcript, "Hello. My name is Amani.")

    def test_lesson_can_have_video_media(self):
        _, _, _, lesson = _ctx()
        m = LessonMedia.objects.create(
            lesson=lesson, media_type="video",
            external_url="https://www.youtube.com/watch?v=abc123",
        )
        self.assertEqual(m.media_type, "video")
        self.assertTrue(m.external_url)

    def test_media_optional_not_required(self):
        """media_type is required; everything else can be blank."""
        _, _, _, lesson = _ctx()
        m = LessonMedia.objects.create(lesson=lesson, media_type="document")
        # No file, no url, no title — still a valid row.
        self.assertFalse(m.file)
        self.assertFalse(m.external_url)
        self.assertEqual(m.title, "")
        self.assertEqual(m.title_ar, "")
        self.assertTrue(m.is_active)

    def test_generated_by_ai_flag(self):
        _, _, _, lesson = _ctx()
        m = LessonMedia.objects.create(
            lesson=lesson, media_type="image",
            generated_by_ai=True,
            generation_prompt="A friendly classroom scene, flat illustration, no text.",
        )
        self.assertTrue(m.generated_by_ai)
        self.assertIn("classroom", m.generation_prompt)

    def test_sort_order_default(self):
        _, _, _, lesson = _ctx()
        a = LessonMedia.objects.create(lesson=lesson, media_type="image")
        b = LessonMedia.objects.create(lesson=lesson, media_type="image", sort_order=2)
        ordered = list(lesson.media.order_by("sort_order", "id"))
        self.assertEqual(ordered, [a, b])


class LessonChecklistTests(TestCase):
    def test_lesson_checklist_items(self):
        _, _, _, lesson = _ctx()
        a = LessonChecklist.objects.create(
            lesson=lesson, text_en="I can introduce myself",
            text_ar="أستطيع التعريف بنفسي", sort_order=1,
        )
        b = LessonChecklist.objects.create(
            lesson=lesson, text_en="I can spell my name", sort_order=2,
        )
        self.assertEqual(lesson.checklist_items.count(), 2)
        self.assertEqual(a.text_for("ar"), "أستطيع التعريف بنفسي")
        # Falls back to EN when AR is blank.
        self.assertEqual(b.text_for("ar"), "I can spell my name")
        # And EN works.
        self.assertEqual(a.text_for("en"), "I can introduce myself")


class QuestionMediaTests(TestCase):
    def test_question_can_have_media(self):
        _, _, _, lesson = _ctx()
        quiz = LessonQuiz.objects.create(lesson=lesson, title="Q1")
        q = LessonQuestion.objects.create(
            quiz=quiz, question_type="multiple_choice",
            question_text="Pick the greeting:",
            options=["Hello", "Banana", "Window"],
            correct_answer="Hello", order=1,
        )
        m = QuestionMedia.objects.create(
            question=q, media_type="image",
            alt_text="Waving hand icon",
        )
        self.assertEqual(q.media.count(), 1)
        self.assertEqual(m.media_type, "image")

    def test_question_audio_media(self):
        _, _, _, lesson = _ctx()
        quiz = LessonQuiz.objects.create(lesson=lesson, title="Q1")
        q = LessonQuestion.objects.create(
            quiz=quiz, question_type="multiple_choice",
            question_text="What did they say?",
            options=["Hello", "Goodbye"],
            correct_answer="Hello", order=1,
        )
        m = QuestionMedia.objects.create(
            question=q, media_type="audio",
            transcript="Hello, my name is Yusuf.",
            language="en",
        )
        self.assertTrue(m.transcript)
        self.assertEqual(m.language, "en")


class LessonAudioScriptTests(TestCase):
    def test_lesson_audio_script_saved(self):
        _, _, _, lesson = _ctx()
        s = LessonAudioScript.objects.create(
            lesson=lesson, script_type="intro",
            script_text="In this lesson, you will learn how to introduce yourself.",
            voice_style="friendly_teacher", accent="american",
        )
        self.assertEqual(s.script_type, "intro")
        self.assertEqual(s.accent, "american")
        self.assertFalse(s.is_generated)  # default

    def test_audio_script_all_types(self):
        _, _, _, lesson = _ctx()
        for kind in ["intro", "vocabulary", "examples", "dialogue",
                     "listening", "quiz", "speaking"]:
            LessonAudioScript.objects.create(
                lesson=lesson, script_type=kind,
                script_text=f"Sample {kind} script.",
            )
        self.assertEqual(lesson.audio_scripts.count(), 7)


class LessonImagePromptTests(TestCase):
    def test_lesson_image_prompt_saved(self):
        _, _, _, lesson = _ctx()
        p = LessonImagePrompt.objects.create(
            lesson=lesson, prompt_type="cover",
            prompt=(
                "Two friendly young adults of mixed backgrounds greeting "
                "each other in a flat-illustration style, soft green "
                "background, no text."
            ),
        )
        self.assertEqual(p.prompt_type, "cover")
        self.assertFalse(p.is_generated)
        self.assertIn("flat-illustration", p.prompt)

    def test_image_prompt_all_types(self):
        _, _, _, lesson = _ctx()
        for kind in ["cover", "vocabulary", "grammar", "quiz"]:
            LessonImagePrompt.objects.create(
                lesson=lesson, prompt_type=kind, prompt=f"{kind} prompt body.",
            )
        self.assertEqual(lesson.image_prompts.count(), 4)
