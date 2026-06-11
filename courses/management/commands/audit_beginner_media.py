"""Read-only media integrity & audio-speed audit for the Beginner course
(Prompt 18.2B).

This command NEVER writes anything — no regeneration, no approval, no relink,
no delete. It walks the canonical 48 lessons of ``onlenco-beginner`` and reports:

  * image completeness (generated? approved/student-visible? file on disk?
    duplicates? linked to non-canonical lessons?),
  * audio completeness (same), plus
  * the audio-speed picture: the hardcoded client ``playbackRate`` and whether
    any TTS ``speed`` setting exists.

Images come from ``LessonImagePrompt.generated_image`` (approval workflow via
``generation_status``) and audio from ``LessonAudioScript.generated_audio``.
``is_student_visible`` == ``generation_status == "approved" and bool(file)``.

Stdlib only. ``--fail-on-critical`` fails ONLY on structural problems (course
missing / fewer than 48 canonical lessons), never on missing media — an audit
must report first.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from courses.models import (
    Course, CourseUnit, Lesson, LessonAudioScript, LessonImagePrompt,
)

_DEFAULT_SLUG = "onlenco-beginner"
_EXPECTED = 48


def _file_on_disk(filefield) -> bool:
    if not filefield:
        return False
    try:
        return filefield.storage.exists(filefield.name)
    except Exception:
        return False


def _detected_playback_rate():
    """Parse the hardcoded playbackRate from the course lesson templates."""
    rates = {}
    base = Path(settings.BASE_DIR) / "templates" / "courses"
    for name in ("lesson_step.html", "lesson_quiz.html"):
        p = base / name
        if not p.exists():
            continue
        try:
            txt = p.read_text(encoding="utf-8")
        except Exception:
            continue
        m = re.search(r"playbackRate\s*=\s*([0-9]*\.?[0-9]+)", txt)
        if m:
            rates[name] = float(m.group(1))
    return rates


class Command(BaseCommand):
    help = (
        "READ-ONLY audit of Beginner course media (images + audio) and audio "
        "speed. Never regenerates, approves, relinks, or deletes."
    )

    def add_arguments(self, parser):
        parser.add_argument("--course-slug", default=_DEFAULT_SLUG)
        parser.add_argument("--format", choices=["text", "json"], default="text")
        parser.add_argument("--fail-on-critical", action="store_true",
                            help="Exit non-zero only on structural problems "
                                 "(course missing / <48 canonical lessons / 16×3 broken).")

    def handle(self, *args, **options):
        slug = options["course_slug"]
        course = Course.objects.filter(slug=slug).first()

        critical = []
        if course is None:
            critical.append("course_not_found")
            report = {"course_slug": slug, "course_found": False, "critical": critical}
            self._emit(report, options["format"])
            if options["fail_on_critical"]:
                raise CommandError(f"Course not found: {slug!r}")
            return

        units = CourseUnit.objects.filter(course=course).count()
        # Canonical 48 = lessons tagged with a book unit number 1..48.
        canonical = list(
            Lesson.objects.filter(
                course=course, book_unit_number__gte=1, book_unit_number__lte=_EXPECTED,
            ).order_by("book_unit_number", "order", "id")
        )
        if len(canonical) != _EXPECTED:
            # Fallback to platform order so the audit still runs.
            canonical = list(Lesson.objects.filter(course=course).order_by("order", "id"))
        if len(canonical) < _EXPECTED:
            critical.append("fewer_than_48_canonical_lessons")
        if units != 16:
            critical.append("units_not_16")

        # ---- Images (LessonImagePrompt) -----------------------------------
        img = {
            "expected_lessons": _EXPECTED,
            "lessons_with_image": 0, "lessons_missing_image": 0,
            "lessons_with_approved_image": 0, "images_not_approved": 0,
            "image_files_missing_on_disk": 0, "duplicate_image_rows": 0,
            "image_prompt_rows_total": 0,
            "image_rows_with_file": 0, "image_rows_missing_file": 0,
        }
        for le in canonical:
            prompts = list(le.image_prompts.all())
            img["image_prompt_rows_total"] += len(prompts)
            with_file = [p for p in prompts if p.generated_image]
            img["image_rows_with_file"] += len(with_file)
            img["image_rows_missing_file"] += len(prompts) - len(with_file)
            if with_file:
                img["lessons_with_image"] += 1
            else:
                img["lessons_missing_image"] += 1
            if any(p.is_student_visible for p in prompts):
                img["lessons_with_approved_image"] += 1
            elif with_file:
                # has a file but none approved/visible
                img["images_not_approved"] += 1
            for p in with_file:
                if not _file_on_disk(p.generated_image):
                    img["image_files_missing_on_disk"] += 1
            # duplicate = >1 image_prompt row for the same prompt_type on a lesson
            type_counts = Counter(p.prompt_type for p in prompts)
            img["duplicate_image_rows"] += sum(c - 1 for c in type_counts.values() if c > 1)

        # ---- Audio (LessonAudioScript) ------------------------------------
        aud = {
            "lessons_with_audio": 0, "lessons_missing_audio": 0,
            "lessons_with_approved_audio": 0, "audio_not_approved": 0,
            "audio_files_missing_on_disk": 0, "audio_script_rows_total": 0,
            "audio_rows_with_file": 0, "audio_rows_missing_file": 0,
            "audio_duration_available_count": 0, "audio_duration_missing_count": 0,
        }
        for le in canonical:
            scripts = list(le.audio_scripts.all())
            aud["audio_script_rows_total"] += len(scripts)
            with_file = [s for s in scripts if s.generated_audio]
            aud["audio_rows_with_file"] += len(with_file)
            aud["audio_rows_missing_file"] += len(scripts) - len(with_file)
            if with_file:
                aud["lessons_with_audio"] += 1
            else:
                aud["lessons_missing_audio"] += 1
            if any(s.is_student_visible for s in scripts):
                aud["lessons_with_approved_audio"] += 1
            elif with_file:
                aud["audio_not_approved"] += 1
            for s in with_file:
                if not _file_on_disk(s.generated_audio):
                    aud["audio_files_missing_on_disk"] += 1
                meta = s.generation_metadata or {}
                if meta.get("audio_output_seconds"):
                    aud["audio_duration_available_count"] += 1
                else:
                    aud["audio_duration_missing_count"] += 1

        # ---- Non-canonical / leftover media (post-dedupe orphan check) ----
        noncanonical_imgs = (
            LessonImagePrompt.objects
            .filter(lesson__course=course)
            .exclude(lesson__book_unit_number__gte=1, lesson__book_unit_number__lte=_EXPECTED)
            .count()
        )
        noncanonical_audio = (
            LessonAudioScript.objects
            .filter(lesson__course=course)
            .exclude(lesson__book_unit_number__gte=1, lesson__book_unit_number__lte=_EXPECTED)
            .count()
        )

        # ---- Audio speed picture ------------------------------------------
        rates = _detected_playback_rate()
        max_rate = max(rates.values()) if rates else None
        tts_speed_setting = getattr(settings, "AI_TTS_SPEED", None)
        tts_voice = getattr(settings, "AI_TTS_VOICE", "alloy")
        # Every clip is sped up if the player forces a rate > 1.0.
        suspicious_fast = aud["lessons_with_audio"] if (max_rate and max_rate > 1.0) else 0

        report = {
            "course_slug": slug,
            "course_found": True,
            "units": units,
            "canonical_lessons": len(canonical),
            "critical": critical,
            "images": img,
            "audio": aud,
            "noncanonical_image_rows": noncanonical_imgs,
            "noncanonical_audio_rows": noncanonical_audio,
            "audio_speed": {
                "detected_playback_rate": rates,
                "max_playback_rate": max_rate,
                "tts_speed_setting": tts_speed_setting,  # None == not configured (default 1.0)
                "tts_voice_setting": tts_voice,
                "suspicious_fast_audio_count": suspicious_fast,
            },
        }
        self._emit(report, options["format"])

        if options["fail_on_critical"] and critical:
            raise CommandError(f"Critical media-audit problems: {critical}")

    # --------------------------------------------------------------- output
    def _emit(self, report, fmt):
        if fmt == "json":
            self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
            return
        w = self.stdout.write
        w("=" * 72)
        w("Beginner media audit (READ-ONLY)")
        w("=" * 72)
        if not report.get("course_found"):
            w(f"Course '{report['course_slug']}' NOT found. critical={report['critical']}")
            return
        w(f"Course: {report['course_slug']}  units={report['units']}  "
          f"canonical_lessons={report['canonical_lessons']}  critical={report['critical'] or 'none'}")
        im, au, sp = report["images"], report["audio"], report["audio_speed"]
        w("")
        w("Images")
        w("-" * 72)
        for k in ("expected_lessons", "lessons_with_image", "lessons_missing_image",
                  "lessons_with_approved_image", "images_not_approved",
                  "image_files_missing_on_disk", "duplicate_image_rows",
                  "image_prompt_rows_total", "image_rows_with_file",
                  "image_rows_missing_file"):
            w(f"  {k:<34}: {im[k]}")
        w(f"  {'noncanonical_image_rows':<34}: {report['noncanonical_image_rows']}")
        w("")
        w("Audio")
        w("-" * 72)
        for k in ("lessons_with_audio", "lessons_missing_audio",
                  "lessons_with_approved_audio", "audio_not_approved",
                  "audio_files_missing_on_disk", "audio_script_rows_total",
                  "audio_rows_with_file", "audio_rows_missing_file",
                  "audio_duration_available_count", "audio_duration_missing_count"):
            w(f"  {k:<34}: {au[k]}")
        w(f"  {'noncanonical_audio_rows':<34}: {report['noncanonical_audio_rows']}")
        w("")
        w("Audio speed")
        w("-" * 72)
        w(f"  detected_playback_rate        : {sp['detected_playback_rate']}")
        w(f"  max_playback_rate             : {sp['max_playback_rate']}")
        w(f"  tts_speed_setting             : {sp['tts_speed_setting']} (None = default 1.0)")
        w(f"  tts_voice_setting             : {sp['tts_voice_setting']}")
        w(f"  suspicious_fast_audio_count   : {sp['suspicious_fast_audio_count']}")
