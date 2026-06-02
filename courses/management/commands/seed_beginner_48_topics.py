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

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

# Statuses whose lessons are LIVE / reviewed — the seed must never silently
# overwrite their status or review/audit fields (Prompt 14.5 hardening).
PRESERVE_STATUSES = {"approved", "published", "archived"}
# Statuses whose generated content may be refreshed in place (status kept).
UPDATABLE_STATUSES = {"pending_review", "draft", "changes_requested", "in_review"}

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

    # Content fields safe to refresh on an UPDATABLE lesson. Note: NO status,
    # NO published_at/approved_*/reviewed_* — those are owned by the workflow.
    CONTENT_FIELDS = (
        "title", "title_en", "title_ar", "lesson_type", "cefr_level", "skill",
        "grammar_topic", "vocabulary_topic", "content_html", "content_en",
        "content_ar", "duration_minutes",
    )

    def add_arguments(self, parser):
        parser.add_argument("--confirm", action="store_true",
                            help="Actually write (default is dry-run).")
        parser.add_argument("--dry-run", action="store_true", dest="dry_run",
                            help="Explicit dry-run (no writes); same as omitting --confirm.")
        parser.add_argument("--topic", type=int, default=0,
                            help="Only seed this single topic order (2-48).")
        parser.add_argument("--reseed", action="store_true",
                            help="Rebuild quiz.questions for UPDATABLE topics only "
                                 "(ignored for approved/published/archived).")
        # --- dangerous flags (default behaviour is always safe) ----------
        parser.add_argument("--update-reviewed-content", action="store_true",
                            dest="update_reviewed_content",
                            help="Refresh CONTENT of approved/published lessons "
                                 "(status still preserved). Requires --confirm.")
        parser.add_argument("--reset-status", action="store_true", dest="reset_status",
                            help="DANGEROUS: reset matched lessons to pending_review "
                                 "(can unpublish live lessons).")
        parser.add_argument("--i-understand-this-can-unpublish", action="store_true",
                            dest="ack_unpublish",
                            help="Required acknowledgement for --reset-status.")

    def _content_defaults(self, topic: dict) -> dict:
        return {
            "title": topic["title_en"], "title_en": topic["title_en"],
            "title_ar": topic["title_ar"], "lesson_type": "mixed",
            "cefr_level": topic["cefr_level"], "skill": "speaking",
            "grammar_topic": topic["grammar_topic"],
            "vocabulary_topic": topic["vocabulary_topic"],
            "content_html": topic["content_html"], "content_en": topic["content_html"],
            "content_ar": topic["content_ar"], "duration_minutes": 8,
        }

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

        # --dry-run always wins over --confirm (fail safe).
        is_confirm = options["confirm"] and not options.get("dry_run")
        update_reviewed = options["update_reviewed_content"]
        reset_status = options["reset_status"]
        ack_unpublish = options["ack_unpublish"]
        mode = "WRITE" if is_confirm else "DRY-RUN"

        # --reset-status is dangerous and must be explicit + acknowledged +
        # scoped to a single topic (never the whole set).
        if reset_status and is_confirm:
            if not ack_unpublish:
                raise CommandError(
                    "--reset-status can UNPUBLISH live lessons. Re-run with "
                    "--i-understand-this-can-unpublish and an explicit --topic=N.")
            if not options["topic"]:
                raise CommandError("--reset-status requires an explicit --topic=N.")

        counters = {"created": 0, "updated_pending": 0, "updated_reviewed": 0,
                    "skipped_published": 0, "skipped_approved": 0,
                    "skipped_archived": 0, "skipped_unknown": 0,
                    "status_changes": 0, "questions": 0, "image_prompts": 0,
                    "audio_scripts": 0, "checklist": 0}
        warnings: list[str] = []
        before_status: dict[int, str] = {}   # lesson.id -> status (existing only)

        known_skills = set(
            Skill.objects.exclude(code__isnull=True).values_list("code", flat=True)
        )

        def write_children(lesson, topic):
            """Idempotently (re)write checklist/media/quiz/questions for a lesson
            whose CONTENT we're allowed to refresh. Touches no status fields."""
            LessonChecklist.objects.filter(lesson=lesson).delete()
            for item in topic["checklist"]:
                LessonChecklist.objects.create(
                    lesson=lesson, sort_order=item["sort_order"],
                    text_en=item["text_en"], text_ar=item["text_ar"], is_active=True)
                counters["checklist"] += 1
            for ip in topic["image_prompts"]:
                LessonImagePrompt.objects.update_or_create(
                    lesson=lesson, prompt_type=ip["prompt_type"],
                    defaults={"prompt": ip["prompt"], "is_generated": False, "sort_order": 0})
                counters["image_prompts"] += 1
            for s in topic["audio_scripts"]:
                LessonAudioScript.objects.update_or_create(
                    lesson=lesson, script_type=s["script_type"],
                    defaults={"script_text": s["script_text"], "voice_style": s["voice_style"],
                              "accent": "american", "is_generated": False,
                              "sort_order": s["sort_order"]})
                counters["audio_scripts"] += 1
            quiz, _ = LessonQuiz.objects.update_or_create(
                lesson=lesson,
                defaults={"title": f"Super Challenge {lesson.order:02d} — {topic['title_en']}",
                          "title_en": f"Super Challenge {lesson.order:02d} — {topic['title_en']}",
                          "title_ar": f"تحدّي {lesson.order:02d} — {topic['title_ar']}",
                          "passing_score": 70, "is_active": True})
            if options["reseed"]:
                quiz.questions.all().delete()
            for q in topic["questions"]:
                qt = TYPE_NORMALISE.get(q["question_type"], q["question_type"])
                md = dict(q.get("metadata") or {})
                cleaned, unknowns_here = [], []
                for code in (md.get("skills") or []):
                    if code in known_skills:
                        cleaned.append(code)
                    else:
                        cleaned.append(FALLBACK_SKILL)
                        unknowns_here.append(code)
                md["skills"] = cleaned or [FALLBACK_SKILL]
                if unknowns_here:
                    warnings.append(
                        f"T{lesson.order:02d} Q{q['order']}: unknown skills "
                        f"{unknowns_here} → mapped to {FALLBACK_SKILL}")
                LessonQuestion.objects.update_or_create(
                    quiz=quiz, order=q["order"],
                    defaults={"question_type": qt, "question_text": q["question_text"],
                              "question_text_en": q["question_text"],
                              "question_text_ar": q.get("question_text_ar", ""),
                              "options": [], "metadata": md,
                              "correct_answer": q.get("correct_answer", ""),
                              "difficulty_score": float(q.get("difficulty_score", 0.5)),
                              "points": 1})
                counters["questions"] += 1

        with transaction.atomic():
            level, _ = CourseLevel.objects.get_or_create(
                code="A0", defaults={"name": "Beginner — Pre-A1", "order": 0})
            # Course exists already; only create if missing (never flip its status here).
            course, _ = Course.objects.get_or_create(
                slug=COURSE_SLUG,
                defaults={"title": COURSE_TITLE, "title_en": COURSE_TITLE, "level": level,
                          "language": "bilingual", "status": "published", "is_free": True,
                          "is_active": True, "drip_enabled": False})

            for topic in topics_data:
                order = topic["order"]
                if order == 1:   # Topic 01 Gold Reference — owned by seed_super_lesson_01.
                    continue
                if not is_confirm:
                    self.stdout.write(f"[{mode}] would seed Topic {order:02d}: {topic['title_en']}")
                    continue

                unit_title = f"Topic {order:02d} — {topic['title_en']}"
                unit, _ = CourseUnit.objects.get_or_create(
                    course=course, order=order,
                    defaults={"title": unit_title, "title_en": unit_title})

                existing = Lesson.objects.filter(course=course, unit=unit, order=order).first()

                if existing is None:
                    # NEW topic → create as pending_review. Never auto-approve/publish.
                    lesson = Lesson.objects.create(
                        course=course, unit=unit, order=order,
                        status="pending_review", is_active=True,
                        **self._content_defaults(topic))
                    counters["created"] += 1
                    write_children(lesson, topic)
                    continue

                before_status[existing.id] = existing.status

                # DANGEROUS: explicit reset-status (already gated above).
                if reset_status and ack_unpublish and options["topic"] == order:
                    existing.status = "pending_review"
                    for f in self.CONTENT_FIELDS:
                        setattr(existing, f, self._content_defaults(topic)[f])
                    existing.save(update_fields=list(self.CONTENT_FIELDS) + ["status", "updated_at"])
                    counters["status_changes"] += 1
                    write_children(existing, topic)
                    self.stdout.write(self.style.WARNING(
                        f"  T{order:02d}: STATUS RESET → pending_review (dangerous flag)."))
                    continue

                if existing.status in PRESERVE_STATUSES:
                    # Live/reviewed lesson: status + review fields are SACRED.
                    if update_reviewed:
                        for f in self.CONTENT_FIELDS:
                            setattr(existing, f, self._content_defaults(topic)[f])
                        existing.save(update_fields=list(self.CONTENT_FIELDS) + ["updated_at"])
                        write_children(existing, topic)
                        counters["updated_reviewed"] += 1
                        self.stdout.write(
                            f"  T{order:02d}: content refreshed; status '{existing.status}' preserved.")
                    else:
                        counters[f"skipped_{existing.status}"] += 1
                        self.stdout.write(
                            f"  T{order:02d}: SKIP — status '{existing.status}' preserved (no content change).")
                elif existing.status in UPDATABLE_STATUSES:
                    for f in self.CONTENT_FIELDS:
                        setattr(existing, f, self._content_defaults(topic)[f])
                    existing.save(update_fields=list(self.CONTENT_FIELDS) + ["updated_at"])
                    write_children(existing, topic)
                    counters["updated_pending"] += 1
                else:
                    counters["skipped_unknown"] += 1
                    warnings.append(f"T{order:02d}: unknown status '{existing.status}' — preserved.")

            # --- SAFETY ASSERTION: no existing status changed unexpectedly ---
            if is_confirm and not reset_status:
                changed = []
                for lid, old in before_status.items():
                    new = Lesson.objects.values_list("status", flat=True).get(id=lid)
                    if new != old:
                        changed.append((lid, old, new))
                if changed:
                    raise CommandError(
                        f"Aborting: {len(changed)} lesson status(es) changed unexpectedly "
                        f"{changed[:5]}. Seed must never alter review/publish status.")

        # Final summary
        if is_confirm:
            self.stdout.write(self.style.SUCCESS(
                f"\n[OK] created={counters['created']} "
                f"updated_pending_review={counters['updated_pending']} "
                f"updated_reviewed_content={counters['updated_reviewed']}"))
            self.stdout.write(
                f"     skipped_published={counters['skipped_published']} "
                f"skipped_approved={counters['skipped_approved']} "
                f"skipped_archived={counters['skipped_archived']} "
                f"skipped_unknown={counters['skipped_unknown']}")
            self.stdout.write(
                f"     status_changes={counters['status_changes']} "
                f"(questions={counters['questions']}, image_prompts={counters['image_prompts']}, "
                f"audio_scripts={counters['audio_scripts']}, checklist={counters['checklist']})")
            if counters["status_changes"] == 0:
                self.stdout.write(self.style.SUCCESS("     ✅ No review/publish status changed."))
            if warnings:
                self.stdout.write(self.style.WARNING(f"\n[WARN] {len(warnings)} warning(s):"))
                for w in warnings[:20]:
                    self.stdout.write(f"  · {w}")
                if len(warnings) > 20:
                    self.stdout.write(f"  ... and {len(warnings) - 20} more")
        else:
            self.stdout.write(self.style.NOTICE(
                "\n[DRY-RUN] No writes. Pass --confirm to actually seed."))
