"""Materialise the in-code A0 curriculum into real DB rows.

What this command does:
  1. Ensures ``CourseLevel(code="A0")`` exists.
  2. Creates / updates 5 ``Course`` rows — one per A0 unit (Hello,
     About Me, Basic Objects, Simple Sentences, Daily Life).
  3. Creates / updates a ``Lesson`` for every topic in
     ``daily_learning.services.a0_templates.A0_TOPICS``.
  4. Creates / updates one ``LessonQuiz`` + ``LessonQuestion`` per
     topic, mirroring the topic's quiz item.
  5. Creates / updates ``AITutorPrompt`` rows from the speaking +
     listening items of each topic, so the in-lesson tutor has a
     curriculum-anchored prompt to drive its first turn.

Idempotent on rerun (uses ``update_or_create`` keyed on slug / order).

Usage:
    python manage.py import_a0_curriculum
    python manage.py import_a0_curriculum --dry-run
    python manage.py import_a0_curriculum --reset   # delete A0 lessons first
"""
from __future__ import annotations

import logging

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from daily_learning.services import a0_templates
from daily_learning.services.a0_templates import (
    UNIT_1_HELLO, UNIT_2_ABOUT_ME, UNIT_3_BASIC_OBJECTS,
    UNIT_4_SIMPLE_SENTENCES, UNIT_5_DAILY_LIFE,
    UNIT_TITLES_AR, UNIT_TITLES_EN,
)

logger = logging.getLogger(__name__)


UNIT_DESCRIPTIONS_EN = {
    1: "Greet people and say your name.",
    2: "Talk about yourself — country, age, job, nationality.",
    3: "Name everyday objects around you.",
    4: "Build simple complete sentences.",
    5: "Describe your daily routine in English.",
}
UNIT_DESCRIPTIONS_AR = {
    1: "ألقِ التحية وقل اسمك.",
    2: "تحدّث عن نفسك — البلد، العمر، العمل، الجنسية.",
    3: "سمِّ الأشياء اليومية من حولك.",
    4: "ابنِ جملاً بسيطة كاملة.",
    5: "صف روتينك اليومي بالإنجليزية.",
}


class Command(BaseCommand):
    help = "Materialise the A0 daily-learning catalog into Course + Lesson + AITutorPrompt rows."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Print intended changes without writing anything.",
        )
        parser.add_argument(
            "--reset", action="store_true",
            help="Delete existing A0 Lessons + AITutorPrompts before importing.",
        )

    def handle(self, *args, **opts):
        dry_run = bool(opts.get("dry_run"))
        reset = bool(opts.get("reset"))

        from courses.models import (
            Course, CourseLevel, Lesson, LessonQuestion, LessonQuiz,
        )
        from tutor.models import AITutorPrompt

        if dry_run:
            self.stdout.write(self.style.WARNING("[DRY RUN] no changes will be written."))

        # 1. CourseLevel A0
        level, level_created = CourseLevel.objects.get_or_create(
            code="A0",
            defaults={"name": "A0 — Absolute beginner", "order": 0, "is_active": True},
        )
        self.stdout.write(self.style.SUCCESS(
            f"CourseLevel A0 {'CREATED' if level_created else 'EXISTS'}: id={level.id}"
        ))

        # 2. Optional reset
        if reset and not dry_run:
            from django.db.models import Q
            qs_lessons = Lesson.objects.filter(course__level=level)
            n_lessons = qs_lessons.count()
            qs_lessons.delete()
            n_prompts = AITutorPrompt.objects.filter(cefr_level="A0").count()
            AITutorPrompt.objects.filter(cefr_level="A0").delete()
            self.stdout.write(self.style.WARNING(
                f"[RESET] deleted {n_lessons} A0 lessons, {n_prompts} A0 tutor prompts"
            ))

        # 3. One Course per Unit
        courses_by_unit: dict[int, "Course"] = {}
        for unit_no in (UNIT_1_HELLO, UNIT_2_ABOUT_ME, UNIT_3_BASIC_OBJECTS,
                        UNIT_4_SIMPLE_SENTENCES, UNIT_5_DAILY_LIFE):
            slug = f"a0-unit-{unit_no}"
            title_en = f"A0 Unit {unit_no} — {UNIT_TITLES_EN[unit_no]}"
            defaults = {
                "title": title_en,
                "level": level,
                "description": UNIT_DESCRIPTIONS_EN[unit_no],
                "status": "published",
                "is_active": True,
                "is_free": True,
            }
            if dry_run:
                self.stdout.write(f"[DRY] Course {slug}: {title_en}")
                courses_by_unit[unit_no] = None
                continue
            try:
                course, c_created = Course.objects.update_or_create(
                    slug=slug, defaults=defaults,
                )
                courses_by_unit[unit_no] = course
                self.stdout.write(
                    f"Course {'created' if c_created else 'updated'}: {slug}"
                )
            except Exception as e:
                self.stderr.write(self.style.ERROR(
                    f"Failed to upsert course {slug}: {e}"
                ))
                courses_by_unit[unit_no] = None

        # 4. One Lesson + LessonQuiz + AITutorPrompt per A0Topic
        per_unit_order: dict[int, int] = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        lessons_created = lessons_updated = quizzes_created = prompts_created = 0

        for topic in a0_templates.A0_TOPICS:
            unit_no = topic.unit
            per_unit_order[unit_no] += 1
            order = per_unit_order[unit_no]
            course = courses_by_unit.get(unit_no)
            if dry_run or course is None:
                self.stdout.write(
                    f"[DRY] Lesson U{unit_no}/{order}: {topic.title_en!r}"
                )
                continue

            lesson_defaults = {
                "title": topic.title_en,
                "lesson_type": "vocabulary",
                "cefr_level": "A0",
                "skill": "vocabulary",
                "status": "published",
                "is_active": True,
                "duration_minutes": 10,
                "content_html": _build_lesson_body(topic),
            }
            lesson, l_created = Lesson.objects.update_or_create(
                course=course, order=order,
                defaults=lesson_defaults,
            )
            if l_created:
                lessons_created += 1
            else:
                lessons_updated += 1

            # LessonQuiz mirroring the topic's quiz item
            quiz_item = next(
                (it for it in topic.items if it.item_type == "quiz"),
                None,
            )
            if quiz_item:
                quiz, q_created = LessonQuiz.objects.update_or_create(
                    lesson=lesson,
                    defaults={
                        "title": f"Quick check — {topic.title_en}",
                        "passing_score": 60,
                        "is_active": True,
                    },
                )
                if q_created:
                    quizzes_created += 1
                # Replace previous questions so import is idempotent.
                LessonQuestion.objects.filter(quiz=quiz).delete()
                LessonQuestion.objects.create(
                    quiz=quiz,
                    question_type="multiple_choice",
                    question_text=quiz_item.question_en,
                    options=list(quiz_item.options),
                    correct_answer=quiz_item.correct_answer,
                    explanation=quiz_item.explanation_en,
                    difficulty_score=0.1,
                    points=1,
                    order=1,
                )

            # AI-tutor prompt — derived from the topic's speaking item.
            speaking_item = next(
                (it for it in topic.items if it.item_type == "speaking"),
                None,
            )
            if speaking_item:
                AITutorPrompt.objects.update_or_create(
                    lesson=lesson,
                    order=1,
                    defaults={
                        "lesson_slug": f"{course.slug}-l{order}",
                        "cefr_level": "A0",
                        "prompt_en": (
                            speaking_item.instructions_en
                            or f"Say: {topic.target_sentence}"
                        ),
                        "prompt_ar": (
                            speaking_item.instructions_ar
                            or f"قل: {topic.target_sentence}"
                        ),
                        "expected_student_answer": topic.target_sentence,
                        "correction_strategy": "echo-and-encourage",
                        "difficulty_score": 0.1,
                        "is_active": True,
                    },
                )
                prompts_created += 1

        self.stdout.write(self.style.SUCCESS(
            f"\nLessons:  created={lessons_created} updated={lessons_updated}\n"
            f"Quizzes:  created={quizzes_created}\n"
            f"Prompts:  created/updated={prompts_created}\n"
            f"Topics processed: {len(a0_templates.A0_TOPICS)}"
        ))


def _build_lesson_body(topic) -> str:
    """Render a small HTML body from the topic's items.

    Keeps the lesson detail page self-contained — the same fields
    the daily plan uses, just in a single static block."""
    word = topic.target_word
    sentence = topic.target_sentence
    quiz_item = next((it for it in topic.items if it.item_type == "quiz"), None)
    parts = [
        f"<h3>Word</h3><p><b>{word}</b></p>",
        f"<h3>Sentence</h3><p>{sentence}</p>",
        "<h3>Listen and repeat</h3>"
        f"<p>Listen, then say <b>{sentence}</b> three times.</p>",
    ]
    if quiz_item:
        parts.append(
            f"<h3>Quick check</h3><p>{quiz_item.question_en}</p>"
        )
    return "\n".join(parts)
