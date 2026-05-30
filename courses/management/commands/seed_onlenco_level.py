"""Seed an Onlenco Course for any non-A0 level (A1 → C2).

Mirrors `seed_onlenco_beginner_48_units` but is parameterised by the
`--level` flag, drawing course slug + 48 unit dicts from
`onlenco_level_descriptors.LEVELS` + `onlenco_level_unit_builder`.

Idempotent — same lookup keys as the A0 seed.
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from courses.models import (
    Course, CourseLevel, CourseUnit, Lesson,
    LessonAudioScript, LessonChecklist, LessonImagePrompt, LessonQuiz,
)
from courses.services.onlenco_beginner_seed_data import (
    build_audio_scripts, build_content_ar, build_content_html,
    build_image_prompts,
)
from courses.services.onlenco_level_descriptors import LEVELS
from courses.services.onlenco_level_unit_builder import build_all_units_for_level


User = get_user_model()


LEVEL_BY_CODE = {lv["code"]: lv for lv in LEVELS}


class Command(BaseCommand):
    help = "Seed an Onlenco course for one CEFR level (A1, A2, B1, B2, C1, or C2)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--level", required=True,
            choices=sorted(LEVEL_BY_CODE),
            help="CEFR level code.",
        )
        parser.add_argument("--quiet", action="store_true")
        parser.add_argument("--dry-run", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        level_code = options["level"]
        level = LEVEL_BY_CODE[level_code]
        quiet = options["quiet"]
        if options["dry_run"]:
            self.stdout.write(self.style.WARNING(
                f"DRY RUN — would seed Course '{level['course_slug']}' "
                f"({level['code']}) with 48 lessons."
            ))
            return

        course_level, _ = CourseLevel.objects.get_or_create(
            code=level_code,
            defaults={"name": f"{level_code} ({level['course_title_en']})", "order": 1},
        )
        teacher = self._system_teacher()
        course, course_created = Course.objects.update_or_create(
            slug=level["course_slug"],
            defaults={
                "title": level["course_title_en"],
                "title_en": level["course_title_en"],
                "title_ar": level["course_title_ar"],
                "description": level["course_desc_en"],
                "description_en": level["course_desc_en"],
                "description_ar": level["course_desc_ar"],
                "level": course_level,
                "teacher": teacher,
                "created_by": teacher,
                "status": "published",
                "is_active": True,
            },
        )

        units = build_all_units_for_level(level)
        n_course_units = (len(units) + CourseUnit.MAX_LESSONS_PER_UNIT - 1) // CourseUnit.MAX_LESSONS_PER_UNIT
        course_units: list[CourseUnit] = []
        for i in range(n_course_units):
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

        counts = {"lessons": 0, "checklist": 0, "img_prompts": 0, "audio_scripts": 0}

        for unit_data in units:
            cu = course_units[(unit_data["n"] - 1) // CourseUnit.MAX_LESSONS_PER_UNIT]
            lesson = self._upsert_lesson(course, cu, unit_data)
            counts["lessons"] += 1
            counts["checklist"] += self._upsert_checklist(lesson, unit_data)
            counts["img_prompts"] += self._upsert_image_prompts(lesson, unit_data)
            counts["audio_scripts"] += self._upsert_audio_scripts(lesson, unit_data)
            LessonQuiz.objects.get_or_create(
                lesson=lesson,
                defaults={
                    "title": f"Quiz — {lesson.title}",
                    "title_en": f"Quiz — {lesson.title}",
                    "title_ar": f"اختبار — {lesson.title_ar}",
                    "is_active": True,
                },
            )

        self.stdout.write(self.style.SUCCESS(
            f"Onlenco {level_code} seeded — "
            f"course={course.title!r}, lessons={counts['lessons']}, "
            f"checklist={counts['checklist']}, prompts={counts['img_prompts']}, "
            f"scripts={counts['audio_scripts']}."
        ))

    def _system_teacher(self):
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

    def _upsert_lesson(self, course, course_unit, unit_data: dict) -> Lesson:
        lesson, _ = Lesson.objects.update_or_create(
            course=course, order=unit_data["n"],
            defaults={
                "unit": course_unit,
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
                defaults={"text_en": text_en, "text_ar": text_ar, "is_active": True},
            )
        LessonChecklist.objects.filter(
            lesson=lesson, sort_order__gt=len(items),
        ).delete()
        return len(items)

    def _upsert_image_prompts(self, lesson: Lesson, unit_data: dict) -> int:
        prompts = build_image_prompts(unit_data)
        for sort_order, (ptype, ptext) in enumerate(prompts, start=1):
            LessonImagePrompt.objects.update_or_create(
                lesson=lesson, prompt_type=ptype,
                defaults={"prompt": ptext, "sort_order": sort_order, "is_generated": False},
            )
        return len(prompts)

    def _upsert_audio_scripts(self, lesson: Lesson, unit_data: dict) -> int:
        scripts = build_audio_scripts(unit_data)
        for sort_order, (stype, voice, stext) in enumerate(scripts, start=1):
            LessonAudioScript.objects.update_or_create(
                lesson=lesson, script_type=stype,
                defaults={
                    "script_text": stext, "voice_style": voice,
                    "accent": "american", "sort_order": sort_order,
                    "is_generated": False,
                },
            )
        return len(scripts)
