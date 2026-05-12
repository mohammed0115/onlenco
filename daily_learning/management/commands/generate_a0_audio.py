"""Generate MP3 audio for every A0 Lesson via OpenAI TTS.

For each `courses.Lesson` under an A0 course, synthesise an MP3 from
the lesson's target sentence and save it to ``Lesson.audio_file``.

The command is **idempotent** — by default it skips lessons that
already have audio (so reruns are cheap). Pass ``--force`` to
re-synthesise everything.

It requires ``settings.AI_API_KEY`` to be configured (same key the
tutor + STT services use). Without it the command short-circuits with
a clear message — front-end falls back to the browser TTS button
already rendered in `daily_plan.html` and `library/detail.html`, so
the absence of recorded MP3s never blocks the UX.

Usage:
    python manage.py generate_a0_audio              # missing-only
    python manage.py generate_a0_audio --force      # overwrite all
    python manage.py generate_a0_audio --dry-run    # report only
    python manage.py generate_a0_audio --library    # also do Library chapters
"""
from __future__ import annotations

import logging
import re

import requests
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)

DEFAULT_VOICE = "alloy"
DEFAULT_MODEL = "tts-1"
MAX_CHARS = 600


def _strip_ar(text: str) -> str:
    """Drop Arabic glyphs so the en-US voice doesn't read codepoints aloud."""
    if not text:
        return ""
    out = re.sub(
        r"[֐-׿؀-ۿݐ-ݿࢠ-ࣿﭐ-﷿ﹰ-﻿]+",
        "",
        text,
    )
    out = re.sub(r"[–—\-]+\s*$", "", out, flags=re.M)
    out = re.sub(r"\s+", " ", out).strip()
    return out


def _synth_bytes(text: str, *, voice: str = DEFAULT_VOICE,
                 model: str = DEFAULT_MODEL) -> bytes | None:
    """Direct synth call — returns raw mp3 bytes or None on failure.

    Sanitises via ``humanize_for_speech`` before hitting the upstream
    so identifiers like `user_answer` or `cefr_level` are never read
    aloud, even if a future caller forgets to pre-clean.
    """
    if not settings.AI_API_KEY or not text:
        return None
    from core.services.text_humanizer import humanize_for_speech
    text = humanize_for_speech(text, language="en") or text
    payload = {
        "model": model,
        "input": text[:MAX_CHARS],
        "voice": voice,
        "format": "mp3",
    }
    try:
        resp = requests.post(
            f"{settings.AI_API_BASE.rstrip('/')}/audio/speech",
            headers={
                "Authorization": f"Bearer {settings.AI_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=(5, 30),
        )
        resp.raise_for_status()
        return resp.content
    except Exception as e:
        logger.warning("TTS synth failed for %r: %s", text[:40], e)
        return None


class Command(BaseCommand):
    help = "Generate MP3 audio for every A0 Lesson via OpenAI TTS."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true",
                            help="Re-synthesise even when audio_file exists.")
        parser.add_argument("--dry-run", action="store_true",
                            help="Report intended work without API calls.")
        parser.add_argument("--library", action="store_true",
                            help="Also synthesise audio for Library A0 chapters.")
        parser.add_argument("--voice", default=DEFAULT_VOICE,
                            help=f"OpenAI TTS voice (default: {DEFAULT_VOICE}).")
        parser.add_argument("--limit", type=int, default=0,
                            help="Cap the number of items per pass (0 = no cap).")

    def handle(self, *args, **opts):
        force = bool(opts.get("force"))
        dry_run = bool(opts.get("dry_run"))
        also_library = bool(opts.get("library"))
        voice = opts.get("voice") or DEFAULT_VOICE
        limit = int(opts.get("limit") or 0)

        if not settings.AI_API_KEY and not dry_run:
            self.stdout.write(self.style.WARNING(
                "AI_API_KEY is not configured. Nothing will be synthesised.\n"
                "The front-end browser-TTS fallback (the 🔊 Listen button) "
                "will continue to work without recorded MP3s."
            ))
            return

        if dry_run:
            self.stdout.write(self.style.WARNING(
                "[DRY RUN] no API calls, no DB writes."
            ))

        done = self._do_lessons(force=force, dry_run=dry_run,
                                voice=voice, limit=limit)
        if also_library:
            done += self._do_library(force=force, dry_run=dry_run,
                                     voice=voice, limit=limit)
        self.stdout.write(self.style.SUCCESS(f"\nTotal items processed: {done}"))

    # ----- Lessons -------------------------------------------------------

    def _do_lessons(self, *, force, dry_run, voice, limit) -> int:
        from courses.models import Lesson
        qs = (
            Lesson.objects
            .filter(course__level__code="A0")
            .order_by("course_id", "order")
        )
        if not force:
            qs = qs.filter(audio_file="")
        if limit:
            qs = qs[:limit]
        lessons = list(qs)
        self.stdout.write(f"\nLessons to process: {len(lessons)}")

        ok = fail = 0
        for lesson in lessons:
            text = self._lesson_tts_text(lesson)
            if not text:
                self.stderr.write(self.style.WARNING(
                    f"  ! lesson {lesson.id} has no usable text — skipped"
                ))
                continue
            if dry_run:
                self.stdout.write(
                    f"  [DRY] lesson {lesson.id} ({lesson.title!r}): "
                    f"{text[:50]!r}"
                )
                ok += 1
                continue
            audio = _synth_bytes(text, voice=voice)
            if not audio:
                fail += 1
                self.stderr.write(self.style.ERROR(
                    f"  ✗ lesson {lesson.id} ({lesson.title!r}): TTS failed"
                ))
                continue
            filename = f"a0-lesson-{lesson.id}.mp3"
            lesson.audio_file.save(filename, ContentFile(audio), save=True)
            ok += 1
            self.stdout.write(
                f"  ✓ lesson {lesson.id} ({lesson.title!r}): {len(audio)} bytes"
            )
        self.stdout.write(self.style.SUCCESS(
            f"Lessons: ok={ok} fail={fail}"
        ))
        return ok

    def _lesson_tts_text(self, lesson) -> str:
        """Decide what to synthesise for this lesson.

        We use the content_html (stripped of HTML) — it already contains
        the target sentence + listen-and-repeat block. Arabic glyphs
        and HTML tags are stripped so the en-US voice doesn't trip.
        """
        body = lesson.content_html or lesson.title or ""
        body = re.sub(r"<[^>]+>", " ", body)        # strip HTML
        body = _strip_ar(body)
        # Cap to a short readable chunk so audio stays under ~15 seconds.
        sentences = re.split(r"(?<=[.!?])\s+", body)
        out = " ".join(s for s in sentences[:3] if s).strip()
        return out

    # ----- Library chapters ---------------------------------------------

    def _do_library(self, *, force, dry_run, voice, limit) -> int:
        try:
            from library.models import Chapter
        except Exception:
            return 0
        qs = (
            Chapter.objects
            .filter(book__level="A0")
            .order_by("book_id", "sort_order")
        )
        if not force:
            qs = qs.filter(audio_file="")
        if limit:
            qs = qs[:limit]
        chapters = list(qs)
        self.stdout.write(f"\nLibrary chapters to process: {len(chapters)}")

        ok = fail = 0
        for ch in chapters:
            text = _strip_ar(ch.body or "")
            if not text:
                continue
            if dry_run:
                self.stdout.write(f"  [DRY] chapter {ch.id}: {text[:50]!r}")
                ok += 1
                continue
            audio = _synth_bytes(text, voice=voice)
            if not audio:
                fail += 1
                continue
            filename = f"a0-chapter-{ch.id}.mp3"
            ch.audio_file.save(filename, ContentFile(audio), save=True)
            ok += 1
        self.stdout.write(self.style.SUCCESS(
            f"Library: ok={ok} fail={fail}"
        ))
        return ok
