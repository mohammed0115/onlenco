"""Seed a smart, level-aware Onlenco curriculum (A0 → C2).

Idempotent: re-running the command never duplicates rows. Keys used:
  Course → slug
  CourseUnit → (course, order)
  Lesson → (course, unit, order)
  LessonQuiz → lesson
  LessonQuestion → (quiz, order)
  Book → (title, level)
  Chapter → (book, sort_order)
  ComprehensionQuestion → (chapter, sort_order)

The command does NOT touch:
  - Subscriptions / pricing
  - AI Tutor models
  - Avatar / lip-sync
  - Any real media files

Author handling: uses the first existing superuser as ``created_by``.
If none exists, falls back to the first staff user. If neither and
``DEBUG=False`` it raises CommandError — never seeds without a real
admin account.

Usage:
    DJANGO_SETTINGS_MODULE=config.settings.development python manage.py seed_smart_curriculum
    DJANGO_SETTINGS_MODULE=config.settings.development python manage.py seed_smart_curriculum --dry-run
"""
from __future__ import annotations

from typing import Optional

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify

from courses.models import (
    Course, CourseLevel, CourseUnit, Lesson, LessonQuiz, LessonQuestion,
)
from library.models import Book, Chapter, ComprehensionQuestion

from ._smart_curriculum_data import (
    BOOKS, COURSES, LEVELS_ORDERED, LEVEL_UNITS,
)


User = get_user_model()


# CEFR level metadata (used to ensure CourseLevel rows exist with sane
# names/ordering before any Course is attached to them).
LEVEL_NAMES = {
    "A0": "Beginner — A0",
    "A1": "Elementary — A1",
    "A2": "Pre-Intermediate — A2",
    "B1": "Intermediate — B1",
    "B2": "Upper-Intermediate — B2",
    "C1": "Advanced — C1",
    "C2": "Mastery — C2",
}


# --- HTML / Arabic rendering ----------------------------------------------

def _list_html(items):
    return "<ul>\n" + "".join(f"  <li>{i}</li>\n" for i in items) + "</ul>"


def _vocab_table_html(pairs):
    rows = "".join(
        f"  <tr><td>{en}</td><td>{ar}</td></tr>\n" for en, ar in pairs
    )
    return (
        "<table>\n"
        "  <thead><tr><th>English</th><th>Arabic</th></tr></thead>\n"
        f"  <tbody>\n{rows}  </tbody>\n"
        "</table>"
    )


def _examples_html(examples):
    items = [f"{en} <em>({ar})</em>" for en, ar in examples]
    return _list_html(items)


def _dialogue_html(dialogue):
    rows = "".join(
        f"  <p><strong>{speaker}:</strong> {en} <em>({ar})</em></p>\n"
        for speaker, en, ar in dialogue
    )
    return rows


def render_lesson_content_html(lesson: dict) -> str:
    """Build the 9-section English content_html for a lesson dict."""
    pairs = lesson["vocab_pairs"]
    return (
        f"<h3>Lesson Goal</h3>\n<p>{lesson['goal_en']}</p>\n\n"
        f"<h3>Key Vocabulary</h3>\n{_vocab_table_html(pairs)}\n\n"
        f"<h3>Grammar Focus</h3>\n<p>{lesson['grammar_en']}</p>\n\n"
        f"<h3>Examples</h3>\n{_examples_html(lesson['examples'])}\n\n"
        f"<h3>Mini Dialogue</h3>\n{_dialogue_html(lesson['dialogue'])}\n\n"
        f"<h3>Practice Activity</h3>\n<p>{lesson['practice_en']}</p>\n\n"
        f"<h3>Speaking Practice</h3>\n<p>{lesson['speaking_en']}</p>\n\n"
        f"<h3>AI Tutor Drill</h3>\n<p>{lesson['ai_drill_en']}</p>\n\n"
        f"<h3>Encouragement</h3>\n<p>You're doing great. Keep going — every small step counts.</p>\n"
    )


def render_lesson_content_ar(lesson: dict) -> str:
    pairs = lesson["vocab_pairs"]
    return (
        f"<h3>هدف الدرس</h3>\n<p>{lesson['goal_ar']}</p>\n\n"
        f"<h3>الكلمات المهمّة</h3>\n{_vocab_table_html(pairs)}\n\n"
        f"<h3>القاعدة</h3>\n<p>{lesson['grammar_ar']}</p>\n\n"
        f"<h3>أمثلة</h3>\n{_examples_html(lesson['examples'])}\n\n"
        f"<h3>تدريب</h3>\n<p>{lesson['practice_ar']}</p>\n\n"
        f"<h3>قبل التحدّث مع المعلّم الذكي</h3>\n<p>{lesson['speaking_ar']}</p>\n\n"
        f"<h3>تعليمات للمعلّم الذكي</h3>\n<p>{lesson['ai_drill_ar']}</p>\n\n"
        f"<h3>تشجيع</h3>\n<p>أنت تتقدّم بشكل جيد. واصل — كل خطوة صغيرة تُحتسب.</p>\n"
    )


# --- author resolution ----------------------------------------------------

def resolve_author() -> Optional[User]:
    """Pick a real account to attribute the seed content to.

    Order:
      1. First superuser.
      2. First staff user (only when DEBUG=True).
      3. None — only allowed when DEBUG=True (dev fixtures).

    In production with no usable account we refuse to proceed so we
    never create rows without provenance.
    """
    su = User.objects.filter(is_superuser=True).order_by("pk").first()
    if su:
        return su
    if getattr(settings, "DEBUG", False):
        staff = User.objects.filter(is_staff=True).order_by("pk").first()
        return staff  # may be None — caller decides
    raise CommandError(
        "seed_smart_curriculum needs a superuser in production. "
        "Create one with `python manage.py createsuperuser` and retry."
    )


# --- core seed logic ------------------------------------------------------

class Command(BaseCommand):
    help = "Seed the Onlenco smart curriculum (A0 → C2) idempotently."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Compute the plan and print counts without writing the DB.",
        )

    def handle(self, *args, **opts):
        dry = bool(opts.get("dry_run"))
        author = resolve_author()
        if author is None and not getattr(settings, "DEBUG", False):
            raise CommandError("No superuser available — refusing to seed.")

        # Count what we'd create so the report is meaningful even on
        # the first run.
        report = {
            "courses": 0, "units": 0, "lessons": 0, "quizzes": 0,
            "questions": 0, "books": 0, "chapters": 0, "comp_q": 0,
        }

        for code in LEVELS_ORDERED:
            level = self._ensure_level(code)
            course_meta = COURSES[code]
            course = self._ensure_course(code, level, course_meta, author, dry)
            report["courses"] += 1

            for u_idx, unit_data in enumerate(LEVEL_UNITS[code], start=1):
                unit = self._ensure_unit(course, u_idx, unit_data, dry)
                report["units"] += 1

                for l_idx, lesson_data in enumerate(unit_data["lessons"], start=1):
                    lesson = self._ensure_lesson(
                        course, unit, l_idx, lesson_data, author, code, dry,
                    )
                    report["lessons"] += 1

                    quiz = self._ensure_quiz(lesson, lesson_data, dry)
                    report["quizzes"] += 1

                    for q_idx, q in enumerate(lesson_data["quiz"], start=1):
                        self._ensure_question(quiz, q_idx, q, dry)
                        report["questions"] += 1

                # Publish the unit only when it has its 3 active lessons.
                if not dry:
                    if unit.lessons.filter(is_active=True).count() >= CourseUnit.MAX_LESSONS_PER_UNIT:
                        if not unit.is_published:
                            unit.is_published = True
                            unit.save(update_fields=["is_published"])

            book_meta = BOOKS[code]
            book = self._ensure_book(code, book_meta, dry)
            report["books"] += 1
            for c_idx, ch in enumerate(book_meta["chapters"], start=1):
                chapter = self._ensure_chapter(book, c_idx, ch, dry)
                report["chapters"] += 1
                for cq_idx, cq in enumerate(ch["questions"], start=1):
                    self._ensure_comp_question(chapter, cq_idx, cq, dry)
                    report["comp_q"] += 1

        self.stdout.write(self.style.SUCCESS(
            f"{'[dry-run] would seed' if dry else 'Seeded'} "
            f"{report['courses']} courses · "
            f"{report['units']} units · "
            f"{report['lessons']} lessons · "
            f"{report['quizzes']} quizzes · "
            f"{report['questions']} lesson Qs · "
            f"{report['books']} books · "
            f"{report['chapters']} chapters · "
            f"{report['comp_q']} comprehension Qs."
        ))

    # ---- ensure_* helpers ----

    def _ensure_level(self, code: str) -> CourseLevel:
        level, _ = CourseLevel.objects.get_or_create(
            code=code,
            defaults={
                "name": LEVEL_NAMES[code],
                "order": LEVELS_ORDERED.index(code) + 1,
                "is_active": True,
            },
        )
        return level

    def _ensure_course(self, code, level, meta, author, dry) -> Course:
        slug = f"onlenco-{code.lower()}"
        defaults = {
            "title": meta["title_en"],
            "title_en": meta["title_en"],
            "title_ar": meta["title_ar"],
            "description": meta["summary_en"],
            "description_en": meta["summary_en"],
            "description_ar": meta["summary_ar"],
            "level": level,
            "language": "bilingual",
            "status": "published",
            "is_free": meta.get("is_free", False),
            "is_active": True,
            "drip_enabled": True,
            "created_by": author,
        }
        if dry:
            return Course(slug=slug, **defaults)
        course, _ = Course.objects.update_or_create(slug=slug, defaults=defaults)
        return course

    def _ensure_unit(self, course, order, unit_data, dry) -> CourseUnit:
        defaults = {
            "title": unit_data["unit_title_en"],
            "title_en": unit_data["unit_title_en"],
            "title_ar": unit_data["unit_title_ar"],
            "is_active": True,
        }
        if dry:
            return CourseUnit(course=course, order=order, **defaults)
        unit, _ = CourseUnit.objects.update_or_create(
            course=course, order=order, defaults=defaults,
        )
        return unit

    def _ensure_lesson(self, course, unit, order, lesson, author, cefr_code, dry) -> Lesson:
        defaults = {
            "title": lesson["title_en"],
            "title_en": lesson["title_en"],
            "title_ar": lesson["title_ar"],
            "lesson_type": lesson["type"],
            "cefr_level": cefr_code,
            "skill": lesson["type"],
            "grammar_topic": lesson["grammar"],
            "vocabulary_topic": lesson["vocab"],
            "content_html": render_lesson_content_html(lesson),
            "content_en": render_lesson_content_html(lesson),
            "content_ar": render_lesson_content_ar(lesson),
            "status": "published",
            "is_active": True,
            "created_by": author,
        }
        if dry:
            return Lesson(course=course, unit=unit, order=order, **defaults)
        ls, _ = Lesson.objects.update_or_create(
            course=course, unit=unit, order=order, defaults=defaults,
        )
        return ls

    def _ensure_quiz(self, lesson, lesson_data, dry) -> LessonQuiz:
        title_en = f"Quiz: {lesson_data['title_en']}"
        title_ar = f"اختبار: {lesson_data['title_ar']}"
        if dry:
            return LessonQuiz(lesson=lesson, title=title_en, title_en=title_en, title_ar=title_ar)
        quiz, _ = LessonQuiz.objects.update_or_create(
            lesson=lesson,
            defaults={"title": title_en, "title_en": title_en, "title_ar": title_ar},
        )
        return quiz

    def _ensure_question(self, quiz, order, q, dry) -> LessonQuestion:
        # multiple_choice rule: correct_answer must be in options.
        options = list(q.get("options") or [])
        if q["type"] == "multiple_choice" and q["correct"] not in options:
            options = options + [q["correct"]]
        defaults = {
            "question_type": q["type"],
            "question_text": q["q_en"],
            "question_text_en": q["q_en"],
            "question_text_ar": q["q_ar"],
            "options": options,
            "correct_answer": q["correct"],
        }
        if dry:
            return LessonQuestion(quiz=quiz, order=order, **defaults)
        qrow, _ = LessonQuestion.objects.update_or_create(
            quiz=quiz, order=order, defaults=defaults,
        )
        return qrow

    def _ensure_book(self, code, meta, dry) -> Book:
        defaults = {
            "author": "Onlenco Academy",
            "category": meta["category"],
            "summary": meta["summary"],
            "is_published": True,
        }
        if dry:
            return Book(title=meta["title"], level=code, **defaults)
        book, _ = Book.objects.update_or_create(
            title=meta["title"], level=code, defaults=defaults,
        )
        return book

    def _ensure_chapter(self, book, sort_order, ch, dry) -> Chapter:
        defaults = {"title": ch["title"], "body": ch["body"]}
        if dry:
            return Chapter(book=book, sort_order=sort_order, **defaults)
        chap, _ = Chapter.objects.update_or_create(
            book=book, sort_order=sort_order, defaults=defaults,
        )
        return chap

    def _ensure_comp_question(self, chapter, sort_order, cq, dry):
        defaults = {
            "question": cq["q"],
            "options": list(cq.get("options") or []),
            "correct_answer": cq["correct"],
            "source": "seed",
        }
        if dry:
            return ComprehensionQuestion(chapter=chapter, sort_order=sort_order, **defaults)
        row, _ = ComprehensionQuestion.objects.update_or_create(
            chapter=chapter, sort_order=sort_order, defaults=defaults,
        )
        return row
