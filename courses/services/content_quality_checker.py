"""Phase 11 — Content quality checker.

Pure, deterministic, no AI. Given a Lesson, returns:

    { "score": 0-100, "passed": bool, "flags": [ {severity, code, message, where}, ... ] }

`severity` is one of: "error" (blocks approval), "warning" (mention but OK),
"info" (notice). The score starts at 100 and each flag subtracts.

The checker is called by:
  * `check_generated_content_quality` management command
  * Review-detail view (live recompute)
  * `review_workflow.approve()` (refused if any "error" flag)
"""
from __future__ import annotations

import re
from typing import Iterable

from django.db.models import QuerySet


# ---------------------------------------------------------------------------
# Tunables.
# ---------------------------------------------------------------------------

REQUIRED_SECTIONS = [
    "lesson-goal", "new-language", "vocabulary", "key-language",
    "how-to-form", "visual-guide", "mini-dialogue",
    "listening-practice", "speaking-practice", "ai-tutor-drill",
    "checklist",
]

# Per-band forbidden question_types.
A0_FORBIDDEN = {"listen_and_type", "translate_to_english"}
A0_PLUS_FORBIDDEN = {"listen_and_type"}

SPEAKING_TYPES = {
    "speak_this_sentence", "ai_roleplay_prompt",
    "pronunciation_check", "speaking_prompt",
}
LISTENING_TYPES = {
    "listen_and_choose", "listen_and_type", "sound_to_word",
}

BRAND_NEEDLES = (
    "English for Everyone", "DK Publishing", "Duolingo",
    " owl ", "DK style", "Duolingo style",
)

# Severity deductions.
DEDUCTIONS = {
    "error":   12,
    "warning": 4,
    "info":    0,
}

PASS_THRESHOLD = 85


# ---------------------------------------------------------------------------
# Public API.
# ---------------------------------------------------------------------------

def check_lesson_quality(lesson) -> dict:
    """Run every rule. Returns the canonical dict."""
    flags: list[dict] = []
    flags.extend(_check_structure(lesson))
    flags.extend(_check_questions(lesson))
    flags.extend(_check_media(lesson))
    flags.extend(_check_arabic(lesson))

    score = 100
    for f in flags:
        score -= DEDUCTIONS.get(f["severity"], 0)
    score = max(0, min(100, score))

    return {
        "score":  score,
        "passed": score >= PASS_THRESHOLD and not _has_errors(flags),
        "flags":  flags,
    }


def save_quality_result(lesson, result: dict) -> None:
    """Persist score + flag-codes onto the Lesson for the dashboard list."""
    lesson.quality_score = int(result["score"])
    lesson.quality_flags = [
        {"severity": f["severity"], "code": f["code"], "message": f["message"]}
        for f in result["flags"]
    ]
    lesson.save(update_fields=["quality_score", "quality_flags", "updated_at"])


# ---------------------------------------------------------------------------
# Rules.
# ---------------------------------------------------------------------------

def _flag(severity: str, code: str, message: str, where: str = "") -> dict:
    return {"severity": severity, "code": code, "message": message, "where": where}


def _has_errors(flags: Iterable[dict]) -> bool:
    return any(f["severity"] == "error" for f in flags)


def _check_structure(lesson) -> list[dict]:
    out: list[dict] = []
    content = lesson.content_html or ""
    for sec in REQUIRED_SECTIONS:
        if f'class="{sec}"' not in content:
            out.append(_flag("error", "missing_section",
                             f"content_html is missing section '{sec}'", sec))
    # Checklist items
    from courses.models import LessonChecklist
    n = LessonChecklist.objects.filter(lesson=lesson, is_active=True).count()
    if n < 4:
        out.append(_flag("error", "few_checklist_items",
                         f"Only {n} checklist items (need ≥ 4)", "checklist"))
    return out


def _check_questions(lesson) -> list[dict]:
    out: list[dict] = []
    quiz = getattr(lesson, "quiz", None)
    if quiz is None:
        out.append(_flag("error", "no_quiz", "Lesson has no LessonQuiz", "quiz"))
        return out
    qs = list(quiz.questions.all().order_by("order"))
    n = len(qs)
    if n < 8:
        out.append(_flag("error", "too_few_questions",
                         f"Challenge has {n} questions (need ≥ 8)", "challenge"))
    if n > 12:
        out.append(_flag("warning", "too_many_questions",
                         f"Challenge has {n} questions (recommended ≤ 12)", "challenge"))

    types_in_topic = [q.question_type for q in qs]

    # A0/A1 forbidden types.
    order = lesson.order or 0
    if 1 <= order <= 12:
        for qt in types_in_topic:
            if qt in A0_FORBIDDEN:
                out.append(_flag("error", "forbidden_type_a0",
                                 f"Topic ≤ 12 must not use '{qt}'", qt))
    elif 13 <= order <= 24:
        for qt in types_in_topic:
            if qt in A0_PLUS_FORBIDDEN:
                out.append(_flag("error", "forbidden_type_a0_plus",
                                 f"Topic 13-24 must not use '{qt}'", qt))

    # Speaking-placeholder cap.
    speak_count = sum(1 for qt in types_in_topic if qt in SPEAKING_TYPES)
    if speak_count > 3:
        out.append(_flag("error", "too_many_speaking",
                         f"{speak_count} speaking placeholders (max 3)", "challenge"))

    # Listening coverage.
    if not any(qt in LISTENING_TYPES for qt in types_in_topic):
        out.append(_flag("warning", "no_listening_question",
                         "No listening-skill question in this topic", "challenge"))

    # Speaking coverage.
    if not any(qt in SPEAKING_TYPES for qt in types_in_topic):
        out.append(_flag("warning", "no_speaking_question",
                         "No speaking-skill question in this topic", "challenge"))

    # First Q easy.
    if qs:
        first = qs[0]
        if (first.difficulty_score or 0) > 0.4:
            out.append(_flag("warning", "first_question_too_hard",
                             f"First question difficulty {first.difficulty_score} > 0.4",
                             f"Q{first.order}"))
        # Last Q speaking/roleplay.
        last = qs[-1]
        if last.question_type not in SPEAKING_TYPES:
            out.append(_flag("warning", "last_question_not_speaking",
                             f"Last question is {last.question_type} (want speaking/roleplay)",
                             f"Q{last.order}"))

    # Skills + fallback detection.
    from learning_core.models import Skill
    valid_codes = set(
        Skill.objects.exclude(code__isnull=True).values_list("code", flat=True)
    )
    for q in qs:
        skills = (q.metadata or {}).get("skills") or []
        if not skills:
            out.append(_flag("error", "no_skills",
                             f"Q{q.order} ({q.question_type}) has no metadata.skills",
                             f"Q{q.order}"))
            continue
        for code in skills:
            if code not in valid_codes:
                out.append(_flag("warning", "unknown_skill",
                                 f"Q{q.order} uses unknown skill '{code}'",
                                 f"Q{q.order}"))
            if code == "general_beginner":
                out.append(_flag("warning", "fallback_skill",
                                 f"Q{q.order} uses fallback skill 'general_beginner'",
                                 f"Q{q.order}"))
    return out


def _check_media(lesson) -> list[dict]:
    out: list[dict] = []
    from courses.models import LessonAudioScript, LessonImagePrompt

    image_count = LessonImagePrompt.objects.filter(lesson=lesson).count()
    if image_count != 4:
        out.append(_flag(
            "error" if image_count < 4 else "warning",
            "image_prompt_count",
            f"Lesson has {image_count} image prompts (expected 4)",
            "image_prompts",
        ))

    audio_count = LessonAudioScript.objects.filter(lesson=lesson).count()
    if audio_count != 6:
        out.append(_flag(
            "error" if audio_count < 6 else "warning",
            "audio_script_count",
            f"Lesson has {audio_count} audio scripts (expected 6)",
            "audio_scripts",
        ))

    # Brand / copyright risk in prompts.
    for ip in LessonImagePrompt.objects.filter(lesson=lesson):
        lower = ip.prompt.lower()
        for needle in BRAND_NEEDLES:
            if needle.lower().strip() in lower:
                out.append(_flag("error", "brand_risk",
                                 f"Image prompt mentions '{needle.strip()}'",
                                 f"image:{ip.prompt_type}"))
        if "no logo" not in lower and "no copyrighted" not in lower and "no brand" not in lower:
            out.append(_flag("warning", "missing_copyright_disclaimer",
                             "Image prompt doesn't include a 'no logos' disclaimer",
                             f"image:{ip.prompt_type}"))

    # Audio script hygiene.
    for s in LessonAudioScript.objects.filter(lesson=lesson):
        if "<" in s.script_text or ">" in s.script_text:
            out.append(_flag("error", "audio_has_html",
                             f"Audio script '{s.script_type}' contains HTML",
                             f"audio:{s.script_type}"))
        if "_" in s.script_text:
            out.append(_flag("error", "audio_has_underscore",
                             f"Audio script '{s.script_type}' contains an underscore",
                             f"audio:{s.script_type}"))

    return out


def _check_arabic(lesson) -> list[dict]:
    out: list[dict] = []
    ar = lesson.content_ar or ""
    en = lesson.content_html or ""
    if not ar.strip():
        out.append(_flag("error", "missing_arabic",
                         "content_ar is empty", "content_ar"))
        return out
    # AR/EN ratio.
    ratio = len(ar) / max(1, len(en))
    if ratio < 0.5:
        out.append(_flag("warning", "arabic_too_short",
                         f"Arabic is {int(ratio * 100)}% of English (recommended ≥ 50%)",
                         "content_ar"))
    # Key sections in AR.
    for sec in ("lesson-goal", "vocabulary", "checklist"):
        if f'class="{sec}"' not in ar:
            out.append(_flag("warning", "arabic_section_missing",
                             f"content_ar missing '{sec}' section",
                             f"ar:{sec}"))
    return out


# ---------------------------------------------------------------------------
# Bulk helpers.
# ---------------------------------------------------------------------------

def quality_summary_for_queryset(qs: QuerySet) -> list[dict]:
    """Run on every lesson in a queryset. Returns list of dicts with
    `lesson_id`, `order`, `title`, `score`, `flags_count`, `error_count`."""
    out = []
    for lesson in qs.iterator():
        result = check_lesson_quality(lesson)
        out.append({
            "lesson_id":    lesson.pk,
            "order":        lesson.order,
            "title":        lesson.title,
            "status":       lesson.status,
            "score":        result["score"],
            "passed":       result["passed"],
            "flags_count":  len(result["flags"]),
            "error_count":  sum(1 for f in result["flags"] if f["severity"] == "error"),
        })
    return out
