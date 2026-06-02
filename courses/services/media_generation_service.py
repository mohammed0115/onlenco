"""Prompt 15 — controlled AI media generation pilot.

Generates images (from LessonImagePrompt) and audio (from LessonAudioScript)
for Batch 1 ONLY, strictly through the ai_usage wrapper (never the provider
directly). Generated media starts at ``needs_review`` and is invisible to
students until ``approved``. Budget-gated; failures never crash the batch.
"""
from __future__ import annotations

import logging
from decimal import Decimal

from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone

from ai_usage import constants as AC
from ai_usage.models import AIUsageLog
from ai_usage.services import ai_client

logger = logging.getLogger(__name__)


def _est(name: str, default: str) -> Decimal:
    try:
        return Decimal(str(getattr(settings, name, default)))
    except Exception:
        return Decimal(default)


def unsafe_image_reason(prompt_text: str) -> str | None:
    """Flag a brand/IP word as a WHOLE word, so a safe disclaimer ('no logos',
    'trademarked styling') never trips it — only true brand names do."""
    import re
    low = (prompt_text or "").lower()
    for w in getattr(settings, "ONLENCO_MEDIA_UNSAFE_WORDS", []):
        w = w.lower().strip()
        if w and re.search(rf"\b{re.escape(w)}\b", low):
            return f"unsafe_word:{w}"
    return None


def unsafe_audio_reason(script_text: str) -> str | None:
    t = script_text or ""
    if "<" in t or ">" in t:
        return "html_in_script"
    if "_" in t:
        return "underscore_in_script"
    return None


def _latest_usage_log():
    """The AIUsageLog the wrapper just wrote (single-threaded command)."""
    return AIUsageLog.objects.order_by("-id").first()


def _role_for(actor) -> str:
    if actor is None:
        return AC.ROLE_SYSTEM
    profile = getattr(actor, "profile", None)
    try:
        if getattr(actor, "is_superuser", False) or (profile and profile.is_admin):
            return AC.ROLE_ADMIN
        if profile and profile.is_teacher:
            return AC.ROLE_TEACHER
    except Exception:
        pass
    return AC.ROLE_SYSTEM


# ---------------------------------------------------------------------------
# Single-item generation
# ---------------------------------------------------------------------------

def generate_lesson_image(prompt_obj, *, actor=None, replace=False) -> tuple[str, str]:
    """Returns (outcome, detail). outcome ∈ generated/skipped/failed."""
    lesson = prompt_obj.lesson
    if prompt_obj.generated_image and not replace:
        return ("skipped", "already_generated")
    bad = unsafe_image_reason(prompt_obj.prompt)
    if bad:
        prompt_obj.generation_status = "failed"
        prompt_obj.gen_error_message = bad
        prompt_obj.save(update_fields=["generation_status", "gen_error_message", "updated_at"])
        return ("failed", bad)
    model = "gpt-image-1-mini"
    try:
        png = ai_client.generate_image(
            prompt_obj.prompt, size=getattr(settings, "ONLENCO_MEDIA_IMAGE_SIZE", "1024x1024"),
            model=model, user=actor, role=_role_for(actor),
            feature=AC.FEATURE_MEDIA_GENERATION, lesson_id=lesson.id,
            metadata={"purpose": prompt_obj.prompt_type, "kind": "image"},
        )
    except Exception as exc:
        prompt_obj.generation_status = "failed"
        prompt_obj.gen_error_message = str(exc)[:500]
        prompt_obj.ai_usage_log = _latest_usage_log()
        prompt_obj.save(update_fields=["generation_status", "gen_error_message",
                                       "ai_usage_log", "updated_at"])
        return ("failed", str(exc)[:120])
    prompt_obj.generated_image.save(
        f"t{lesson.order:02d}_{prompt_obj.prompt_type}.png", ContentFile(png), save=False)
    prompt_obj.is_generated = True
    prompt_obj.generation_status = "needs_review"
    prompt_obj.generated_at = timezone.now()
    prompt_obj.gen_provider = AC.PROVIDER_OPENAI
    prompt_obj.gen_model_name = model
    prompt_obj.gen_error_message = ""
    prompt_obj.ai_usage_log = _latest_usage_log()
    prompt_obj.save()
    return ("generated", "needs_review")


def generate_lesson_audio(script_obj, *, actor=None, replace=False) -> tuple[str, str]:
    lesson = script_obj.lesson
    if script_obj.generated_audio and not replace:
        return ("skipped", "already_generated")
    bad = unsafe_audio_reason(script_obj.script_text)
    if bad:
        script_obj.generation_status = "failed"
        script_obj.gen_error_message = bad
        script_obj.save(update_fields=["generation_status", "gen_error_message", "updated_at"])
        return ("failed", bad)
    model = getattr(settings, "AI_TTS_MODEL", "tts-1")
    voice = getattr(settings, "AI_TTS_VOICE", "alloy")
    try:
        audio = ai_client.synthesize_speech(
            script_obj.script_text[:3000], voice=voice, model=model,
            user=actor, role=_role_for(actor), feature=AC.FEATURE_TTS,
            lesson_id=lesson.id,
            metadata={"purpose": script_obj.script_type, "kind": "audio"},
        )
    except Exception as exc:
        script_obj.generation_status = "failed"
        script_obj.gen_error_message = str(exc)[:500]
        script_obj.ai_usage_log = _latest_usage_log()
        script_obj.save(update_fields=["generation_status", "gen_error_message",
                                       "ai_usage_log", "updated_at"])
        return ("failed", str(exc)[:120])
    log = _latest_usage_log()
    script_obj.generated_audio.save(
        f"t{lesson.order:02d}_{script_obj.script_type}.mp3", ContentFile(audio), save=False)
    script_obj.is_generated = True
    script_obj.generation_status = "needs_review"
    script_obj.generated_at = timezone.now()
    script_obj.gen_provider = AC.PROVIDER_OPENAI
    script_obj.gen_model_name = model
    script_obj.gen_error_message = ""
    script_obj.ai_usage_log = log
    md = dict(script_obj.generation_metadata or {})
    if log:
        md["audio_output_seconds"] = log.audio_output_seconds
    script_obj.generation_metadata = md
    script_obj.save()
    return ("generated", "needs_review")


# ---------------------------------------------------------------------------
# Review lifecycle
# ---------------------------------------------------------------------------

def mark_media_approved(media_obj, reviewer, note=""):
    media_obj.generation_status = "approved"
    media_obj.reviewed_by = reviewer
    media_obj.reviewed_at = timezone.now()
    if note:
        media_obj.review_notes = note
    media_obj.save(update_fields=["generation_status", "reviewed_by", "reviewed_at",
                                  "review_notes", "updated_at"])
    return media_obj


def mark_media_rejected(media_obj, reviewer, note=""):
    media_obj.generation_status = "rejected"
    media_obj.reviewed_by = reviewer
    media_obj.reviewed_at = timezone.now()
    if note:
        media_obj.review_notes = note
    media_obj.save(update_fields=["generation_status", "reviewed_by", "reviewed_at",
                                  "review_notes", "updated_at"])
    return media_obj


def get_media_for_student(lesson, purpose, media_type):
    """Return an approved media file (or None) for a lesson section."""
    if media_type == "image":
        obj = lesson.image_prompts.filter(prompt_type=purpose,
                                          generation_status="approved").first()
        return obj.generated_image if (obj and obj.generated_image) else None
    obj = lesson.audio_scripts.filter(script_type=purpose,
                                      generation_status="approved").first()
    return obj.generated_audio if (obj and obj.generated_audio) else None
