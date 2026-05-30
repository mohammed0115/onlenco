"""Phase 7 — AI Tutor inside Challenge: context builder.

Sanitises and assembles the tight, single-question context the AI
prompt needs. NEVER includes the student's full history, PII, raw HTML,
or any underscores/JSON the model might accidentally read aloud.

Public API:
  build_question_context(user, session, question, answer=None,
                         interaction_type='wrong_answer_explanation') -> dict
"""
from __future__ import annotations

import re
from typing import Optional


# Strip HTML tags and collapse whitespace. Strict but cheap — we never
# want raw `<div class="...">` in a prompt.
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_UNDERSCORE_WORD_RE = re.compile(r"_+")


def _clean(text) -> str:
    if not text:
        return ""
    s = _HTML_TAG_RE.sub(" ", str(text))
    s = _UNDERSCORE_WORD_RE.sub(" ", s)
    s = s.replace("​", "").replace("\xa0", " ")
    s = _WS_RE.sub(" ", s).strip()
    return s


def _lang_pref(user) -> str:
    pref = getattr(getattr(user, "profile", None), "preferred_language", "en")
    return "ar" if (pref or "").startswith("ar") else "en"


def _user_level(user) -> str:
    profile = getattr(user, "learning_profile", None)
    if profile is None:
        return ""
    return (profile.current_cefr_level or "").upper()


def _skill_codes_for(question) -> list[str]:
    try:
        from learning_core.services import skill_resolver
        return [s.code for s in skill_resolver.get_question_skills(question) if s.code]
    except Exception:
        return []


def _mastery_for_skills(user, skill_codes) -> dict[str, float]:
    if not skill_codes:
        return {}
    try:
        from learning_core.models import SkillMastery
        rows = SkillMastery.objects.filter(
            user=user, skill__code__in=skill_codes,
        ).select_related("skill")
        return {r.skill.code: round(float(r.mastery_score), 1) for r in rows}
    except Exception:
        return {}


def _mistake_type(user, question) -> str:
    try:
        from learning_core.models import StudentMistake
        m = StudentMistake.objects.filter(
            user=user, question=question, mastered=False,
        ).first()
        return m.mistake_type if m else ""
    except Exception:
        return ""


def _lesson_title(session) -> str:
    return _clean(getattr(getattr(session, "lesson", None), "title", "")) or ""


def _cefr_level(session) -> str:
    return getattr(getattr(session, "lesson", None), "cefr_level", "") or ""


def build_question_context(
    user, session, question, *, answer=None,
    interaction_type: str = "wrong_answer_explanation",
) -> dict:
    """Return a sanitised dict the prompt template can consume.

    Caller responsibilities:
      * Pass `answer=None` for use-cases that don't have a specific
        ChallengeAnswer (e.g. roleplay start, end-of-challenge advice).
      * Pass `interaction_type` so the prompt can switch output shape.
    """
    skill_codes = _skill_codes_for(question)
    mastery = _mastery_for_skills(user, skill_codes)
    user_answer_raw = ""
    is_correct = None
    if answer is not None:
        user_answer_raw = _clean(answer.user_answer)
        is_correct = bool(answer.is_correct)

    return {
        # ---- Identity (NO names, NO emails) ----
        "user_lang_pref":    _lang_pref(user),
        "user_level":        _user_level(user),

        # ---- Lesson / question scoping ----
        "lesson_title":      _lesson_title(session),
        "cefr_level":        _cefr_level(session),
        "question_type":     getattr(question, "question_type", "") or "",
        "question_text":     _clean(getattr(question, "question_text", "")),
        "question_text_ar":  _clean(getattr(question, "question_text_ar", "")),
        "correct_answer":    _clean(getattr(question, "correct_answer", "")),

        # ---- Answer state ----
        "user_answer":       user_answer_raw,
        "is_correct":        is_correct,

        # ---- Adaptive state ----
        "skill_codes":       skill_codes,
        "mastery":           mastery,
        "mistake_type":      _mistake_type(user, question),

        # ---- Routing ----
        "interaction_type":  interaction_type,
    }


# ---------------------------------------------------------------------------
# Prompt assembly — strictly contained per use-case.
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are Onlenco AI Tutor.\n"
    "Use American English. The learner is a beginner.\n"
    "Keep your answer SHORT (3 to 4 sentences max).\n"
    "Correct only ONE mistake. Be encouraging.\n"
    "Do not read symbols or underscores. Do not output JSON.\n"
    "Stay inside the current question and lesson.\n"
    "Reply with plain text only.\n"
)


def system_prompt() -> str:
    return _SYSTEM_PROMPT


def render_user_prompt(ctx: dict) -> str:
    """Compose the user-role prompt — plain text, no tags, no JSON."""
    needs_ar = ctx.get("user_lang_pref") == "ar"
    extra = (
        " Also include a one-sentence Arabic explanation after the English."
        if needs_ar else ""
    )
    parts = [f"Lesson: {ctx['lesson_title'] or '(beginner)'}"]
    if ctx.get("cefr_level"):
        parts.append(f"Level: {ctx['cefr_level']}")
    parts.append(f"Question: {ctx['question_text']}")
    if ctx.get("user_answer"):
        parts.append(f"Student answered: {ctx['user_answer']}")
    if ctx.get("correct_answer"):
        parts.append(f"Correct answer: {ctx['correct_answer']}")
    if ctx.get("mistake_type"):
        parts.append(f"Mistake type: {ctx['mistake_type']}")
    interaction = ctx.get("interaction_type", "")
    if interaction == "wrong_answer_explanation":
        parts.append(
            "Task: Briefly explain in 1-2 sentences WHY the student's "
            "answer is wrong, give ONE simple rule, then ONE short example."
            + extra
        )
    elif interaction == "speaking_feedback":
        parts.append(
            "Task: Give 3 short bullets of friendly speaking advice "
            "(pronunciation focus). No more than 3 bullets total." + extra
        )
    elif interaction == "roleplay":
        parts.append(
            "Task: Open a SHORT beginner roleplay tied to this question. "
            "Ask ONE simple question only. No more than 1 sentence." + extra
        )
    elif interaction == "end_advice":
        parts.append(
            "Task: Give ONE encouraging sentence about what the student "
            "should practice next." + extra
        )
    elif interaction == "mistake_explanation":
        parts.append(
            "Task: Explain this past mistake in 1-2 sentences for "
            "a beginner." + extra
        )
    return "\n".join(parts)


def hash_prompt(prompt: str) -> str:
    import hashlib
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:32]
