"""Seed Topics 02-48 of the Onlenco Beginner course.

Topic 01 (Introducing Yourself) is the Gold Reference — handled by
`seed_super_lesson_01`. This command does NOT touch it.

Every new lesson is created with:
    status = "pending_review"
    is_active = True

That keeps them HIDDEN from students (the student querysets filter on
`status="published"`) while letting teachers/admins see them in the
admin for review.

The content was authored offline by a 6-agent workflow and stored in
`courses/data/beginner_topics_data.json`. This command:
  1. Loads that JSON.
  2. Idempotently upserts Course + Units + Lessons + Quizzes + Questions
     + LessonImagePrompt + LessonAudioScript + LessonChecklist.
  3. Normalises legacy question_types (`multiple_choice` → `tap_choice`).
  4. Remaps unknown skill codes to `general_beginner` with a warning.

Flags:
  --dry-run            (default if neither --confirm nor --topic given)
  --confirm            actually write
  --topic=N            only seed Topic N (overrides full-set)
  --reseed             clear quiz.questions before re-creating (per topic)
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from courses.models import (
    Course, CourseLevel, CourseUnit, Lesson, LessonAudioScript,
    LessonChecklist, LessonImagePrompt, LessonQuestion, LessonQuiz,
)
from learning_core.models import Skill


logger = logging.getLogger(__name__)


COURSE_SLUG  = "onlenco-beginner"
COURSE_TITLE = "Onlenco Beginner English Foundation"
DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "beginner_topics_data.json"

# Legacy → preferred question_type. Same data shape, just renamed.
TYPE_NORMALISE = {"multiple_choice": "tap_choice"}

FALLBACK_SKILL = "general_beginner"


class Command(BaseCommand):
    help = "Seed Topics 02-48 of the Onlenco Beginner course (pending_review)."

    def add_arguments(self, parser):
        parser.add_argument("--confirm", action="store_true",
                            help="Actually write (default is dry-run).")
        parser.add_argument("--topic", type=int, default=0,
                            help="Only seed this single topic order (2-48).")
        parser.add_argument("--reseed", action="store_true",
                            help="Wipe existing quiz.questions before re-creating.")

    def handle(self, *args, **options):
        if not DATA_FILE.exists():
            self.stderr.write(self.style.ERROR(
                f"Data file missing: {DATA_FILE}. Run the workflow first.",
            ))
            return

        with DATA_FILE.open("r", encoding="utf-8") as fh:
            topics_data = json.load(fh)

        # Filter to a single topic if requested.
        if options["topic"]:
            topics_data = [t for t in topics_data if t["order"] == options["topic"]]
            if not topics_data:
                self.stderr.write(self.style.ERROR(
                    f"No topic with order={options['topic']} in data file.",
                ))
                return

        is_confirm = options["confirm"]
        mode = "WRITE" if is_confirm else "DRY-RUN"

        # Counters
        n_topics_created = n_topics_updated = 0
        n_questions = n_image_prompts = n_audio_scripts = n_checklist = 0
        n_topics_pending_review = 0
        warnings: list[str] = []

        # Build the skill-code cache for the warning path.
        known_skills = set(
            Skill.objects.exclude(code__isnull=True)
            .values_list("code", flat=True)
        )

        # Ensure the course + level exist (Phase 8 already did this; we
        # do it defensively so the command can run standalone).
        with transaction.atomic():
            level, _ = CourseLevel.objects.get_or_create(
                code="A0", defaults={"name": "Beginner — Pre-A1", "order": 0},
            )
            course, _ = Course.objects.update_or_create(
                slug=COURSE_SLUG,
                defaults={
                    "title": COURSE_TITLE, "title_en": COURSE_TITLE,
                    "level": level, "language": "bilingual",
                    "status": "published", "is_free": True,
                    "is_active": True, "drip_enabled": False,
                },
            )

            for topic in topics_data:
                order = topic["order"]

                # Skip Topic 1 — owned by seed_super_lesson_01.
                if order == 1:
                    continue

                unit_title = f"Topic {order:02d} — {topic['title_en']}"
                if not is_confirm:
                    self.stdout.write(f"[{mode}] would seed Topic {order:02d}: {topic['title_en']}")
                    continue

                # 1) Unit
                unit, _ = CourseUnit.objects.update_or_create(
                    course=course, order=order,
                    defaults={"title": unit_title, "title_en": unit_title},
                )

                # 2) Lesson — created/updated as "pending_review".
                lesson, was_new = Lesson.objects.update_or_create(
                    course=course, unit=unit, order=order,
                    defaults={
                        "title":            topic["title_en"],
                        "title_en":         topic["title_en"],
                        "title_ar":         topic["title_ar"],
                        "lesson_type":      "mixed",
                        "cefr_level":       topic["cefr_level"],
                        "skill":            "speaking",
                        "grammar_topic":    topic["grammar_topic"],
                        "vocabulary_topic": topic["vocabulary_topic"],
                        "content_html":     topic["content_html"],
                        "content_en":       topic["content_html"],
                        "content_ar":       topic["content_ar"],
                        "duration_minutes": 8,
                        # Critical: pending_review until a teacher approves.
                        "status":           "pending_review",
                        "is_active":        True,
                    },
                )
                n_topics_pending_review += 1
                if was_new:
                    n_topics_created += 1
                else:
                    n_topics_updated += 1

                # 3) Checklist
                LessonChecklist.objects.filter(lesson=lesson).delete()
                for item in topic["checklist"]:
                    LessonChecklist.objects.create(
                        lesson=lesson, sort_order=item["sort_order"],
                        text_en=item["text_en"], text_ar=item["text_ar"],
                        is_active=True,
                    )
                    n_checklist += 1

                # 4) Image prompts (4)
                for ip in topic["image_prompts"]:
                    LessonImagePrompt.objects.update_or_create(
                        lesson=lesson, prompt_type=ip["prompt_type"],
                        defaults={"prompt": ip["prompt"],
                                  "is_generated": False, "sort_order": 0},
                    )
                    n_image_prompts += 1

                # 5) Audio scripts (6)
                for s in topic["audio_scripts"]:
                    LessonAudioScript.objects.update_or_create(
                        lesson=lesson, script_type=s["script_type"],
                        defaults={
                            "script_text":  s["script_text"],
                            "voice_style":  s["voice_style"],
                            "accent":       "american",
                            "is_generated": False,
                            "sort_order":   s["sort_order"],
                        },
                    )
                    n_audio_scripts += 1

                # 6) Quiz + Questions
                quiz, _ = LessonQuiz.objects.update_or_create(
                    lesson=lesson,
                    defaults={
                        "title":         f"Super Challenge {order:02d} — {topic['title_en']}",
                        "title_en":      f"Super Challenge {order:02d} — {topic['title_en']}",
                        "title_ar":      f"تحدّي {order:02d} — {topic['title_ar']}",
                        "passing_score": 70,
                        "is_active":     True,
                    },
                )

                if options["reseed"]:
                    quiz.questions.all().delete()

                for q in topic["questions"]:
                    qt = TYPE_NORMALISE.get(q["question_type"], q["question_type"])
                    md = dict(q.get("metadata") or {})

                    # Remap unknown skill codes to the fallback.
                    skills = md.get("skills") or []
                    cleaned, unknowns_here = [], []
                    for code in skills:
                        if code in known_skills:
                            cleaned.append(code)
                        else:
                            cleaned.append(FALLBACK_SKILL)
                            unknowns_here.append(code)
                    md["skills"] = cleaned or [FALLBACK_SKILL]
                    if unknowns_here:
                        warnings.append(
                            f"T{order:02d} Q{q['order']}: unknown skills "
                            f"{unknowns_here} → mapped to {FALLBACK_SKILL}"
                        )

                    LessonQuestion.objects.update_or_create(
                        quiz=quiz, order=q["order"],
                        defaults={
                            "question_type":    qt,
                            "question_text":    q["question_text"],
                            "question_text_en": q["question_text"],
                            "question_text_ar": q.get("question_text_ar", ""),
                            "options":          [],   # metadata.options is the source
                            "metadata":         md,
                            "correct_answer":   q.get("correct_answer", ""),
                            "difficulty_score": float(q.get("difficulty_score", 0.5)),
                            "points":           1,
                        },
                    )
                    n_questions += 1

                self.stdout.write(
                    f"[{mode}] Topic {order:02d}: {len(topic['questions'])} questions, "
                    f"{len(topic['checklist'])} checklist, "
                    f"4 image prompts, 6 audio scripts"
                )

        # Final summary
        if is_confirm:
            self.stdout.write(self.style.SUCCESS(
                f"\n[OK] {n_topics_created} topics created, "
                f"{n_topics_updated} updated, "
                f"{n_topics_pending_review} now pending_review."
            ))
            self.stdout.write(
                f"     {n_questions} questions, {n_image_prompts} image prompts, "
                f"{n_audio_scripts} audio scripts, {n_checklist} checklist items."
            )
            if warnings:
                self.stdout.write(self.style.WARNING(
                    f"\n[WARN] {len(warnings)} skill-remap warning(s):"
                ))
                for w in warnings[:20]:
                    self.stdout.write(f"  · {w}")
                if len(warnings) > 20:
                    self.stdout.write(f"  ... and {len(warnings) - 20} more")
        else:
            self.stdout.write(self.style.NOTICE(
                f"\n[DRY-RUN] No writes. Pass --confirm to actually seed."
            ))
