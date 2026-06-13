"""Transfer full courses (A0–C2) between environments — content + audio.

A robust alternative to ``dumpdata``/``loaddata`` for moving the course
catalog from local → production. ``dumpdata`` is fragile here because
courses carry FKs to ``User`` (teacher/created_by/reviewed_by/approved_by),
``CourseLevel`` and ``CourseUnit`` whose primary keys differ per database.
This command serialises by NATURAL identifiers (course slug, level code,
lesson order) and skips user/file/timestamp fields entirely, so it imports
cleanly into any environment.

What travels: Course, CourseUnit, Lesson, LessonAudioScript,
LessonImagePrompt, LessonChecklist, LessonQuiz + LessonQuestion — i.e. all
the text content. The "listen and repeat" AUDIO is generated on-demand from
each lesson's audio-script text, so it comes with the lesson automatically
(no media files to copy). Uploaded media (video/pdf/generated images) is
NOT transferred.

Export (local)::

    python manage.py transfer_courses --export courses_export.json
    python manage.py transfer_courses --export beginner.json --slugs onlenco-beginner

Import (production — copy the file over first)::

    # clean slate (prod has no students): wipe existing courses, then load
    python manage.py transfer_courses --import courses_export.json --prune
    # or merge (update_or_create by slug; rebuilds each course's children)
    python manage.py transfer_courses --import courses_export.json
"""
from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError
from django.db import models, transaction

from courses.models import (
    Course, CourseLevel, CourseUnit, Lesson, LessonAudioScript,
    LessonChecklist, LessonImagePrompt, LessonQuestion, LessonQuiz,
)

# Fields never serialised: surrogate key, audit timestamps.
_SKIP = {"id", "created_at", "updated_at"}
# Field TYPES never serialised: files (media doesn't transfer across hosts),
# dates (avoid tz/parse pitfalls — none are content-critical here).
_SKIP_TYPES = (models.FileField, models.DateField)


def _scalars(obj) -> dict:
    """Concrete, non-relational, non-file, non-date fields of a model row."""
    out = {}
    for f in obj._meta.concrete_fields:
        if f.is_relation or f.name in _SKIP or isinstance(f, _SKIP_TYPES):
            continue
        out[f.name] = f.value_from_object(obj)
    return out


def _export(slugs):
    qs = Course.objects.select_related("level")
    if slugs:
        qs = qs.filter(slug__in=slugs)
    else:
        qs = qs.exclude(status="archived")
    qs = qs.order_by("level__order", "slug")

    courses = []
    for c in qs:
        units = {u.pk: _scalars(u) for u in CourseUnit.objects.filter(course=c)}
        unit_code = {u.pk: u.code for u in CourseUnit.objects.filter(course=c)}
        lessons = []
        for L in c.lessons.all().order_by("order", "id"):
            quiz = None
            q = getattr(L, "quiz", None)
            if q is not None:
                quiz = {
                    "fields": _scalars(q),
                    "questions": [_scalars(x) for x in q.questions.all().order_by("order", "id")],
                }
            lessons.append({
                "fields": _scalars(L),
                "unit_code": unit_code.get(L.unit_id),
                "audio_scripts": [_scalars(s) for s in L.audio_scripts.all().order_by("sort_order", "id")],
                "image_prompts": [_scalars(p) for p in L.image_prompts.all().order_by("sort_order", "id")],
                "checklist": [_scalars(i) for i in L.checklist_items.all().order_by("sort_order", "id")],
                "quiz": quiz,
            })
        courses.append({
            "fields": _scalars(c),
            "level_code": c.level.code if c.level_id else None,
            "units": list(units.values()),
            "lessons": lessons,
        })
    return {"version": 1, "courses": courses}


@transaction.atomic
def _import(payload, prune):
    if prune:
        # Prod has no students — wipe the whole catalog so unique codes never
        # collide, then rebuild from the export.
        Course.objects.all().delete()

    stats = {"courses": 0, "lessons": 0, "questions": 0}
    for cd in payload["courses"]:
        level = None
        code = cd.get("level_code")
        if code:
            level = CourseLevel.objects.filter(code=code).first()
            if level is None:
                level = CourseLevel.objects.create(
                    code=code, name=code, description="", order=0)

        cf = dict(cd["fields"])
        slug = cf.pop("slug")
        course, _ = Course.objects.update_or_create(
            slug=slug, defaults={**cf, "level": level})

        # Rebuild children from scratch for a deterministic result.
        CourseUnit.objects.filter(course=course).delete()
        course.lessons.all().delete()

        unit_by_code = {}
        for uf in cd.get("units", []):
            u = CourseUnit.objects.create(course=course, **uf)
            unit_by_code[u.code] = u

        for ld in cd["lessons"]:
            unit = unit_by_code.get(ld.get("unit_code"))
            lesson = Lesson.objects.create(course=course, unit=unit, **ld["fields"])
            for s in ld["audio_scripts"]:
                LessonAudioScript.objects.create(lesson=lesson, **s)
            for p in ld["image_prompts"]:
                LessonImagePrompt.objects.create(lesson=lesson, **p)
            for i in ld["checklist"]:
                LessonChecklist.objects.create(lesson=lesson, **i)
            if ld["quiz"]:
                quiz = LessonQuiz.objects.create(lesson=lesson, **ld["quiz"]["fields"])
                for qq in ld["quiz"]["questions"]:
                    LessonQuestion.objects.create(quiz=quiz, **qq)
                    stats["questions"] += 1
            stats["lessons"] += 1
        stats["courses"] += 1
    return stats


class Command(BaseCommand):
    help = "Export/import full courses (content + audio scripts) between environments."

    def add_arguments(self, parser):
        parser.add_argument("--export", metavar="FILE", help="Write the catalog to FILE.")
        parser.add_argument("--import", dest="import_file", metavar="FILE",
                            help="Load the catalog from FILE.")
        parser.add_argument("--slugs", nargs="*", default=None,
                            help="Limit export to these course slug(s).")
        parser.add_argument("--prune", action="store_true",
                            help="On import: DELETE all existing courses first (no students).")

    def handle(self, *args, **opts):
        if bool(opts["export"]) == bool(opts["import_file"]):
            raise CommandError("Choose exactly one of --export or --import.")

        if opts["export"]:
            payload = _export(opts["slugs"])
            with open(opts["export"], "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=2)
            n = len(payload["courses"])
            lessons = sum(len(c["lessons"]) for c in payload["courses"])
            self.stdout.write(self.style.SUCCESS(
                f"✓ Exported {n} course(s), {lessons} lesson(s) → {opts['export']}"))
            for c in payload["courses"]:
                self.stdout.write(
                    f"  - [{c['level_code']}] {c['fields']['slug']} "
                    f"({len(c['lessons'])} lessons)")
            return

        # import
        with open(opts["import_file"], encoding="utf-8") as fh:
            payload = json.load(fh)
        if opts["prune"]:
            self.stdout.write(self.style.WARNING(
                "--prune: deleting ALL existing courses before import."))
        stats = _import(payload, prune=opts["prune"])
        self.stdout.write(self.style.SUCCESS(
            f"✓ Imported {stats['courses']} course(s), {stats['lessons']} lesson(s), "
            f"{stats['questions']} question(s)."))
