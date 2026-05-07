"""Build a safe, compact tutor context from the student's adaptive profile.

Returns a dict with primitives only — no model instances, so it can be
included in a prompt without leaking PII or huge payloads. Keep it cheap.
"""
from __future__ import annotations

from typing import Iterable

from learning_core.models import StudentLearningProfile, UserError
from learning_core.services.weakness_engine import get_top_weaknesses

MAX_RECENT_ERRORS = 5
MAX_WEAKNESSES = 3


def build_tutor_context(user, conversation_topic: str = "") -> dict:
    profile = StudentLearningProfile.objects.filter(user=user).first()
    cefr_level = (
        (profile.current_cefr_level if profile else None)
        or getattr(getattr(user, "profile", None), "cefr_level", None)
        or "B1"
    )
    language_pref = getattr(getattr(user, "profile", None), "preferred_language", "en")

    weaknesses = get_top_weaknesses(user, limit=MAX_WEAKNESSES)
    recent_errors: Iterable[UserError] = (
        UserError.objects.filter(user=user)
        .select_related("skill", "grammar_topic")
        .order_by("-created_at")[:MAX_RECENT_ERRORS]
    )

    return {
        "cefr_level": cefr_level,
        "language_preference": language_pref,
        "topic": conversation_topic or "",
        "top_weaknesses": [
            {
                "skill": w.skill.name if w.skill else None,
                "grammar_topic": w.grammar_topic.name if w.grammar_topic else None,
                "priority": round(w.priority_score, 1),
            }
            for w in weaknesses
        ],
        "recent_errors": [
            {
                "fragment": e.original_text[:120],
                "explanation": e.explanation[:200],
                "type": e.error_type,
            }
            for e in recent_errors
        ],
    }


def render_context_block(ctx: dict) -> str:
    """Render the context as a short text block to inject into the system prompt."""
    lines = [
        f"Student CEFR level: {ctx.get('cefr_level', 'B1')}.",
        f"Preferred language: {ctx.get('language_preference', 'en')}.",
    ]
    if ctx.get("topic"):
        lines.append(f"Topic: {ctx['topic']}.")
    if ctx.get("top_weaknesses"):
        bits = []
        for w in ctx["top_weaknesses"]:
            label = w.get("grammar_topic") or w.get("skill") or "general"
            bits.append(f"{label} (priority {w['priority']})")
        lines.append("Top weaknesses: " + "; ".join(bits) + ".")
    if ctx.get("recent_errors"):
        lines.append("Recent mistakes:")
        for e in ctx["recent_errors"]:
            lines.append(f" - [{e['type']}] {e['fragment']}")
    return "\n".join(lines)
