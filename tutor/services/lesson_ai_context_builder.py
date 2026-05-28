"""Build a tutor-scoped system prompt from a `courses.Lesson`.

The tutor's voice-call infrastructure (existing tutor app) accepts a free
text `system_prompt`. For the Onlenco Beginner course we want a *scoped*
drill, not a generic chat — every prompt the tutor sends must stay inside
the lesson's vocabulary, grammar, and CEFR level.

`build_lesson_tutor_prompt(lesson)` returns the assembled instruction
string. Pure function (reads the Lesson; no DB writes). The tutor view
calls it and passes the result to the model on call start.
"""
from __future__ import annotations

from typing import Optional

from courses.models import Lesson, LessonChecklist


SYSTEM_INSTRUCTION = """
You are a friendly American-English tutor for an Arabic-speaking
beginner. Speak slowly and clearly using General American English.
""".strip()

CORRECTION_RULES = """
Correction style:
- One correction at a time. Acknowledge the student's effort first.
- Keep your turns under 12 words.
- Never say underscores, brackets, or punctuation symbols out loud.
- Don't read placeholder words like 'TODO' or 'pending'.
- If the student speaks Arabic, encourage them to try again in English;
  give a single short Arabic hint only if they're stuck.
""".strip()

SAFETY_FALLBACK = """
Safety:
- If the student asks about anything outside this lesson, gently steer
  them back: 'Let's stay with today's topic — we'll cover that later.'
- Do not advise on medical, legal, or financial questions.
""".strip()

ARABIC_SUPPORT = """
Arabic support:
- The student's first language is Arabic. When they look confused, give
  a one-sentence Arabic hint, then return to English immediately.
- Do not narrate the prompt in Arabic by default.
""".strip()

BEGINNER_STYLE_MARKERS = (
    "American English", "slowly", "short", "encourage", "beginner",
)


def build_lesson_tutor_prompt(
    lesson: Lesson,
    *,
    student_name: Optional[str] = None,
    cefr_override: Optional[str] = None,
) -> str:
    """Compose the tutor's system prompt for one Lesson.

    `student_name` is used to personalise the greeting; pass `None` to
    use a generic opener.
    `cefr_override` lets the caller force a CEFR level for the drill
    (useful when adapting an A0 student to A1 content slowly).
    """
    cefr = cefr_override or lesson.cefr_level or "A0"
    greet = (
        f"Greet the student by name ({student_name}) and remind them of "
        f"today's topic in one short sentence."
        if student_name else
        "Greet the student warmly and name today's topic in one short sentence."
    )
    new_language = (lesson.grammar_topic or "").strip() or "(see content_html)"
    vocab = (lesson.vocabulary_topic or "").strip() or "(see content_html)"
    speaking_goal = _extract_speaking_goal(lesson)
    checklist_items = _checklist_can_dos(lesson)

    parts = [
        SYSTEM_INSTRUCTION,
        "",
        "Lesson context:",
        f"- Unit:   {lesson.order} — {lesson.title}",
        f"- Level:  {cefr} (Beginner)",
        f"- New language: {new_language}",
        f"- Allowed vocabulary: {vocab}",
        f"- Speaking task: {speaking_goal}",
        "",
        "Completion criteria:",
        f"- Student successfully produces at least 3 correct sentences using the new language.",
        f"- Student can answer your 'Can you …?' check based on the unit's can-do list:",
    ] + [f"    • {can_do}" for can_do in checklist_items] + [
        "",
        CORRECTION_RULES,
        "",
        ARABIC_SUPPORT,
        "",
        SAFETY_FALLBACK,
        "",
        f"Start now: {greet}",
    ]
    return "\n".join(parts)


def _extract_speaking_goal(lesson: Lesson) -> str:
    """Return the speaking_goal from the seeded content (best-effort).

    We rely on the section structure `<h3>10. Speaking Practice</h3><p>…</p>`
    that `build_content_html` ships. Falls back to a generic line.
    """
    html = lesson.content_html or ""
    needle = "<h3>10. Speaking Practice</h3>"
    if needle in html:
        tail = html.split(needle, 1)[1]
        # Read the contents of the next <p>…</p>.
        if "<p>" in tail and "</p>" in tail:
            start = tail.index("<p>") + len("<p>")
            end = tail.index("</p>", start)
            from html import unescape
            return unescape(tail[start:end]).strip()
    return "Help the student build and say 3 short sentences using today's new language."


def _checklist_can_dos(lesson: Lesson, max_items: int = 4) -> list[str]:
    items = list(
        LessonChecklist.objects.filter(lesson=lesson, is_active=True)
        .order_by("sort_order")
        .values_list("text_en", flat=True)[:max_items]
    )
    return items or ["(no checklist items defined)"]
