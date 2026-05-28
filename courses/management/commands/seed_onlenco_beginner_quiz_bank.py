"""Seed the Quiz Bank for the Onlenco Beginner course.

Depends on `seed_onlenco_beginner_48_units` having run first (the Course
+ 48 Lessons + 48 LessonQuizzes must exist). Populates each LessonQuiz
with 8–12 original `LessonQuestion` rows, plus a `QuestionMedia`
placeholder for the listening question.

Idempotent: questions keyed by (quiz, order). Re-running overwrites
question text in place — admin edits would be lost. Same trade-off as
P04.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from courses.models import (
    Course, Lesson, LessonQuestion, LessonQuiz, QuestionMedia,
)
from courses.services.onlenco_beginner_quiz_builder import build_questions_for_unit
from courses.services.onlenco_beginner_seed_data import UNITS


COURSE_SLUG = "onlenco-beginner"


class Command(BaseCommand):
    help = (
        "Populate the Quiz Bank for the Onlenco Beginner course — 9 "
        "original questions per Learning Unit. Idempotent."
    )

    def add_arguments(self, parser):
        parser.add_argument("--quiet", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        quiet = options["quiet"]
        try:
            course = Course.objects.get(slug=COURSE_SLUG)
        except Course.DoesNotExist:
            self.stderr.write(self.style.ERROR(
                f"Course '{COURSE_SLUG}' not found. "
                f"Run `seed_onlenco_beginner_48_units` first."
            ))
            return

        # Lessons indexed by their unit order (1..48).
        lessons_by_order = {
            lesson.order: lesson
            for lesson in Lesson.objects.filter(course=course)
        }
        if len(lessons_by_order) != 48:
            self.stderr.write(self.style.WARNING(
                f"Expected 48 lessons, found {len(lessons_by_order)}. "
                f"Continuing anyway."
            ))

        totals = {"quizzes": 0, "questions": 0, "audio_placeholders": 0}

        for unit in UNITS:
            lesson = lessons_by_order.get(unit["n"])
            if lesson is None:
                continue
            quiz, _ = LessonQuiz.objects.get_or_create(
                lesson=lesson,
                defaults={
                    "title": f"Quiz — {lesson.title}",
                    "title_en": f"Quiz — {lesson.title}",
                    "title_ar": f"اختبار — {lesson.title_ar}",
                    "is_active": True,
                },
            )
            totals["quizzes"] += 1

            built = build_questions_for_unit(unit)
            for q in built:
                audio_required = q.pop("_audio_required", False)
                audio_script = q.pop("_audio_script", "")
                order = q["order"]
                question, _ = LessonQuestion.objects.update_or_create(
                    quiz=quiz, order=order,
                    defaults={
                        "question_type":    q["question_type"],
                        "question_text":    q["question_text"],
                        "question_text_en": q["question_text_en"],
                        "question_text_ar": q["question_text_ar"],
                        "options":          q.get("options", []),
                        "correct_answer":   q["correct_answer"],
                        "explanation":      q.get("explanation", ""),
                        "explanation_ar":   q.get("explanation_ar", ""),
                        "difficulty_score": q.get("difficulty_score", 0.3),
                        "points":           q.get("points", 1),
                    },
                )
                totals["questions"] += 1

                if audio_required:
                    QuestionMedia.objects.update_or_create(
                        question=question, media_type="audio",
                        defaults={
                            "transcript": audio_script,
                            "language": "en",
                            "is_active": True,
                            "sort_order": 1,
                            # No file — set during P08 batch audio generation.
                            "generation_prompt": (
                                f"American English, friendly teacher voice, "
                                f"slow beginner pace, 1 sentence: \"{audio_script}\""
                            ),
                        },
                    )
                    totals["audio_placeholders"] += 1

            if not quiet:
                self.stdout.write(
                    f"  U{unit['n']:02d} {lesson.title} → {len(built)} questions"
                )

        self.stdout.write(self.style.SUCCESS(
            f"Quiz Bank seeded — quizzes={totals['quizzes']}, "
            f"questions={totals['questions']}, "
            f"audio_placeholders={totals['audio_placeholders']}."
        ))
