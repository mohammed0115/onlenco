"""Diagnose per-step lesson media (audio + image) visibility. READ-ONLY.

    python manage.py inspect_lesson_media --course-id=1 --lesson-id=1
    python manage.py inspect_lesson_media --lesson-id=1 --step=intro

For each step it reports whether an audio script / image prompt exists, its
generation + review status, the file path/URL, whether the file actually
exists in storage, whether a student would see it, and — when not visible —
the reason (not_generated / needs_review / rejected / missing_file /
mapping_missing). Modifies nothing.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from courses.models import Lesson

# Steps that carry a LessonAudioScript (script_type). `finish` has no audio.
AUDIO_STEP_KINDS = ["intro", "vocabulary", "examples", "dialogue", "listening", "speaking"]
# Image-prompt mapping mirrors the lesson_step view.
IMAGE_STEP_MAP = {"vocabulary": "vocabulary", "examples": "grammar", "dialogue": "grammar", "finish": "quiz"}


class Command(BaseCommand):
    help = "Diagnose per-step lesson media visibility (read-only)."

    def add_arguments(self, parser):
        parser.add_argument("--course-id", type=int, default=None)
        parser.add_argument("--lesson-id", type=int, required=True)
        parser.add_argument("--step", type=str, default=None)

    def handle(self, *args, **opts):
        try:
            lesson = Lesson.objects.select_related("course").get(pk=opts["lesson_id"])
        except Lesson.DoesNotExist:
            raise CommandError(f"Lesson {opts['lesson_id']} not found.")
        if opts["course_id"] and lesson.course_id != opts["course_id"]:
            raise CommandError(
                f"Lesson {lesson.pk} belongs to course {lesson.course_id}, not {opts['course_id']}."
            )

        self.stdout.write(self.style.MIGRATE_HEADING(
            f"Lesson #{lesson.pk} — {lesson.title!r}  (course={lesson.course_id}, status={lesson.status})"
        ))

        steps = [opts["step"]] if opts["step"] else AUDIO_STEP_KINDS
        for step in steps:
            self._report_audio(lesson, step)
            self._report_image(lesson, step)

    # ------------------------------------------------------------------ audio
    def _report_audio(self, lesson, step):
        script = lesson.audio_scripts.filter(script_type=step).first()
        if not script:
            self.stdout.write(f"  [{step}] audio : MISSING SCRIPT (reason=mapping_missing)")
            return
        has_file = bool(script.generated_audio)
        file_exists, url = self._file_state(script.generated_audio if has_file else None)
        visible = script.is_student_visible
        reason = self._audio_reason(script, has_file, file_exists, visible)
        flag = self.style.SUCCESS("VISIBLE") if visible and file_exists else self.style.WARNING(reason)
        self.stdout.write(
            f"  [{step}] audio : status={script.generation_status} file={'yes' if has_file else 'no'} "
            f"file_exists={file_exists} student_visible={visible} -> {flag}"
            + (f"  url={url}" if url else "")
            + (f"  err={script.gen_error_message}" if script.gen_error_message else "")
        )

    @staticmethod
    def _audio_reason(script, has_file, file_exists, visible):
        if visible and file_exists:
            return "ok"
        status = script.generation_status
        if status == "rejected":
            return "rejected"
        if status == "needs_review":
            return "needs_review"
        if not has_file:
            return "not_generated"
        if status == "approved" and not file_exists:
            return "missing_file"
        return status or "not_generated"

    # ------------------------------------------------------------------ image
    def _report_image(self, lesson, step):
        pt = IMAGE_STEP_MAP.get(step)
        if not pt:
            return
        prompt = lesson.image_prompts.filter(prompt_type=pt).order_by("sort_order").first()
        if not prompt:
            self.stdout.write(f"  [{step}] image : MISSING PROMPT (type={pt})")
            return
        has_file = bool(prompt.generated_image)
        file_exists, url = self._file_state(prompt.generated_image if has_file else None)
        visible = prompt.is_student_visible
        flag = self.style.SUCCESS("VISIBLE") if visible and file_exists else self.style.WARNING(
            prompt.generation_status or "not_generated")
        self.stdout.write(
            f"  [{step}] image : type={pt} status={prompt.generation_status} file={'yes' if has_file else 'no'} "
            f"file_exists={file_exists} student_visible={visible} -> {flag}"
            + (f"  url={url}" if url else "")
        )

    # ------------------------------------------------------------------ files
    @staticmethod
    def _file_state(filefield):
        if not filefield:
            return False, ""
        try:
            exists = filefield.storage.exists(filefield.name)
        except Exception:
            exists = False
        try:
            url = filefield.url
        except Exception:
            url = ""
        return exists, url
