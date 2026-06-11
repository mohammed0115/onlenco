"""Seed the Onlenco Beginner course — 48 Learning Units, all original content.

CANONICAL SOURCE (Prompt 18.2): this command is the single owner of the
``onlenco-beginner`` course (16 CourseUnits × 3 Lessons = 48). Other beginner
seeds (e.g. ``seed_beginner_48_topics``) skip this slug when this 16×3 structure
is present, to avoid duplicate lessons. Keep the 16×3 layout here.

Reads from `courses.services.onlenco_beginner_seed_data.UNITS` and persists:

  * One `Course` (idempotent by slug `onlenco-beginner`).
  * 16 `CourseUnit` rows, each grouping 3 of the 48 Lessons.
  * 48 `Lesson` rows (one per topic), bilingual content_html + content_ar.
  * `LessonChecklist` items (2–4 per Lesson).
  * `LessonImagePrompt` rows (4 prompt_types per Lesson) — placeholders for
    P07 batch image generation, no media files generated here.
  * `LessonAudioScript` rows (6 script_types per Lesson) — placeholders for
    P08 batch audio generation, no media files generated here.

Idempotency:
  Running the command twice does **not** create duplicate rows. Lookups:
    Course      → slug
    CourseUnit  → (course, order)
    Lesson      → (course, order)
    Checklist   → (lesson, sort_order)
    ImagePrompt → (lesson, prompt_type)
    AudioScript → (lesson, script_type)

  We use `update_or_create` everywhere so an admin who edits a row gets
  their text overwritten on the next re-seed — that's the trade-off for
  guaranteeing the seed always matches the data file. Custom in-place
  edits should go in the data file, not the DB.

The Quiz Bank (LessonQuestion rows) is **not** seeded by this command —
see Prompt 05 (`seed_onlenco_beginner_quiz_bank`).
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
import csv
from pathlib import Path

from django.conf import settings
from django.db import transaction

from courses.models import (
    Course, CourseLevel, CourseLessonProgress, CourseUnit, Lesson,
    LessonAudioScript, LessonChecklist, LessonImagePrompt, LessonQuiz,
)
from courses.services.onlenco_beginner_seed_data import (
    UNITS, build_audio_scripts, build_content_ar, build_content_html,
    build_image_prompts,
)

User = get_user_model()


BOOK_REFERENCE = "English for Everyone — Level 1 (Beginner), DK 2016"

COURSE_SLUG = "onlenco-beginner"
COURSE_TITLE_EN = "Onlenco Beginner English Foundation"
COURSE_TITLE_AR = "أساس Onlenco للإنجليزية للمبتدئين"
COURSE_DESC_EN = (
    "A 48-unit foundation course in American English for Arabic-speaking "
    "learners starting from zero. Original content; methodology inspired "
    "by published A1 syllabi."
)
COURSE_DESC_AR = (
    "كورس تأسيسي من 48 وحدة في الإنجليزية الأمريكية للمتحدثين بالعربية "
    "الذين يبدؤون من الصفر. محتوى أصلي بالكامل."
)
LEVEL_CODE = "A0"
LEVEL_NAME = "Beginner (A0–A1)"


class Command(BaseCommand):
    help = (
        "Create the Onlenco Beginner course with 48 Learning Units, "
        "all bilingual content, image prompts, and audio scripts. "
        "Idempotent."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--quiet", action="store_true",
            help="Suppress per-unit output (still prints summary).",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Print what would happen without writing to the DB.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        quiet = options["quiet"]
        dry_run = options["dry_run"]

        if dry_run:
            self.stdout.write(self.style.WARNING(
                f"DRY RUN — no DB changes. Would seed {len(UNITS)} units."
            ))
            return

        # Book page numbers come from book_structure.csv (best-effort; the
        # seed still fills book_unit_number from the data file if CSV is absent).
        self.book_pages = self._load_book_pages()

        # --- Course + level + (system) teacher -----------------------------
        level, _ = CourseLevel.objects.get_or_create(
            code=LEVEL_CODE, defaults={"name": LEVEL_NAME, "order": 1},
        )
        teacher = self._system_teacher()
        course, course_created = Course.objects.update_or_create(
            slug=COURSE_SLUG,
            defaults={
                "title": COURSE_TITLE_EN,
                "title_en": COURSE_TITLE_EN,
                "title_ar": COURSE_TITLE_AR,
                "description": COURSE_DESC_EN,
                "description_en": COURSE_DESC_EN,
                "description_ar": COURSE_DESC_AR,
                "level": level,
                "teacher": teacher,
                "created_by": teacher,
                "status": "published",
                "is_active": True,
            },
        )
        if not quiet:
            verb = "Created" if course_created else "Updated"
            self.stdout.write(f"{verb} course: {course.title} (id={course.pk})")

        # --- CourseUnit grouping --------------------------------------------
        # 48 lessons / 3 lessons per unit = 16 CourseUnits.
        # CourseUnit titles are simple placeholders; the renderer shows the
        # Lesson title to students, so unit titles only matter in admin.
        n_units = (len(UNITS) + CourseUnit.MAX_LESSONS_PER_UNIT - 1) // CourseUnit.MAX_LESSONS_PER_UNIT
        course_units: list[CourseUnit] = []
        for i in range(n_units):
            cu, _ = CourseUnit.objects.update_or_create(
                course=course, order=i + 1,
                defaults={
                    "title": f"Group {i + 1}",
                    "title_en": f"Group {i + 1}",
                    "title_ar": f"المجموعة {i + 1}",
                    "is_active": True,
                },
            )
            course_units.append(cu)

        # --- Lessons + related rows ----------------------------------------
        counts = {
            "lessons": 0, "checklist": 0,
            "image_prompts": 0, "audio_scripts": 0,
        }
        for unit_data in UNITS:
            cu = course_units[(unit_data["n"] - 1) // CourseUnit.MAX_LESSONS_PER_UNIT]
            lesson = self._upsert_lesson(course, cu, unit_data)
            counts["lessons"] += 1
            counts["checklist"] += self._upsert_checklist(lesson, unit_data)
            counts["image_prompts"] += self._upsert_image_prompts(lesson, unit_data)
            counts["audio_scripts"] += self._upsert_audio_scripts(lesson, unit_data)
            # Every Lesson gets a 1:1 LessonQuiz placeholder so P05 can fill it.
            LessonQuiz.objects.get_or_create(
                lesson=lesson,
                defaults={
                    "title": f"Quiz — {lesson.title}",
                    "title_en": f"Quiz — {lesson.title}",
                    "title_ar": f"اختبار — {lesson.title_ar}",
                    "is_active": True,
                },
            )

            if not quiet:
                self.stdout.write(
                    f"  U{unit_data['n']:02d} {lesson.title} → "
                    f"checklist={lesson.checklist_items.count()} "
                    f"prompts={lesson.image_prompts.count()} "
                    f"scripts={lesson.audio_scripts.count()}"
                )

        self.stdout.write(self.style.SUCCESS(
            f"Onlenco Beginner seed complete — "
            f"course={course.title!r}, "
            f"course_units={len(course_units)}, "
            f"lessons={counts['lessons']}, "
            f"checklist_items={counts['checklist']}, "
            f"image_prompts={counts['image_prompts']}, "
            f"audio_scripts={counts['audio_scripts']}."
        ))

    # --- helpers --------------------------------------------------------

    def _system_teacher(self):
        """Get or create the system author for seed content."""
        user, _ = User.objects.get_or_create(
            username="onlenco-content",
            defaults={
                "email": "content@onlenco.academy",
                "first_name": "Onlenco",
                "last_name": "Content",
                "is_active": True,
            },
        )
        return user

    def _load_book_pages(self) -> dict:
        """Map book unit_number -> page from book_structure.csv (best-effort)."""
        pages = {}
        path = Path(settings.BASE_DIR) / "book_structure.csv"
        if not path.exists():
            return pages
        try:
            with path.open(newline="", encoding="utf-8") as fh:
                for raw in csv.DictReader(fh):
                    try:
                        n = int((raw.get("unit_number") or "").strip())
                        page = int((raw.get("book_page") or "").strip())
                    except (TypeError, ValueError):
                        continue
                    pages[n] = page
        except Exception:
            return {}
        return pages

    def _upsert_lesson(self, course, course_unit, unit_data: dict) -> Lesson:
        n = unit_data["n"]
        lesson, _ = Lesson.objects.update_or_create(
            course=course, order=n,
            defaults={
                "unit": course_unit,
                "book_unit_number": n,
                "book_page": getattr(self, "book_pages", {}).get(n),
                "book_reference": BOOK_REFERENCE,
                "title": unit_data["title_en"],
                "title_en": unit_data["title_en"],
                "title_ar": unit_data["title_ar"],
                "lesson_type": unit_data["lesson_type"],
                "cefr_level": unit_data["cefr"],
                "skill": (
                    "vocabulary" if unit_data["lesson_type"] == "vocabulary"
                    else "grammar" if unit_data["lesson_type"] == "grammar"
                    else unit_data["lesson_type"]
                ),
                "grammar_topic": unit_data["grammar_en"] if unit_data["grammar_en"] != "—" else "",
                "vocabulary_topic": unit_data["vocabulary_en"][:120],
                "content_html": build_content_html(unit_data),
                "content_en": build_content_html(unit_data),
                "content_ar": build_content_ar(unit_data),
                "duration_minutes": unit_data["minutes"],
                "status": "published",
                "is_active": True,
            },
        )
        return lesson

    def _upsert_checklist(self, lesson: Lesson, unit_data: dict) -> int:
        items = unit_data.get("checklist", []) or []
        for i, (text_en, text_ar) in enumerate(items, start=1):
            LessonChecklist.objects.update_or_create(
                lesson=lesson, sort_order=i,
                defaults={
                    "text_en": text_en,
                    "text_ar": text_ar,
                    "is_active": True,
                },
            )
        # Drop any extra rows from a previous larger checklist.
        LessonChecklist.objects.filter(
            lesson=lesson, sort_order__gt=len(items),
        ).delete()
        return len(items)

    def _upsert_image_prompts(self, lesson: Lesson, unit_data: dict) -> int:
        prompts = build_image_prompts(unit_data)
        for sort_order, (ptype, ptext) in enumerate(prompts, start=1):
            LessonImagePrompt.objects.update_or_create(
                lesson=lesson, prompt_type=ptype,
                defaults={
                    "prompt": ptext,
                    "sort_order": sort_order,
                    "is_generated": False,
                },
            )
        return len(prompts)

    def _upsert_audio_scripts(self, lesson: Lesson, unit_data: dict) -> int:
        scripts = build_audio_scripts(unit_data)
        for sort_order, (stype, voice, stext) in enumerate(scripts, start=1):
            LessonAudioScript.objects.update_or_create(
                lesson=lesson, script_type=stype,
                defaults={
                    "script_text": stext,
                    "voice_style": voice,
                    "accent": "american",
                    "sort_order": sort_order,
                    "is_generated": False,
                },
            )
        return len(scripts)
