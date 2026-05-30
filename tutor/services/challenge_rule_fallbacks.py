"""Rule-based fallbacks for the Challenge AI surfaces.

Always available. Used when:
  * `CHALLENGE_AI_ENABLED` is False.
  * `AI_API_KEY` is empty.
  * The LLM call timed out or errored.
  * Per-session or daily quota reached.

The intent is that the student NEVER sees a broken state — there is
always an answer, just possibly a less personalised one.
"""
from __future__ import annotations


# ---------------------------------------------------------------------------
# Wrong-answer fallback.
# ---------------------------------------------------------------------------

def wrong_answer_explanation(ctx: dict) -> tuple[str, str]:
    """Return (en, ar). Driven by `ctx['mistake_type']` when set, otherwise
    a generic encouraging note pointing at the correct answer."""
    correct = ctx.get("correct_answer") or "(see answer)"
    mistake = (ctx.get("mistake_type") or "").lower()

    rules = {
        "wrong_choice": (
            f"Almost! The right choice is \"{correct}\". Read the question once more, then pick the option that matches.",
            f"اقتربت! الخيار الصحيح هو «{correct}». اقرأ السؤال مرة أخرى ثم اختر ما يناسبه.",
        ),
        "spelling": (
            f"You're close. The correct spelling is \"{correct}\". Write it slowly, one letter at a time.",
            f"أنت قريب. التهجئة الصحيحة هي «{correct}». اكتبها ببطء، حرفاً حرفاً.",
        ),
        "word_order": (
            f"Word order matters in English. The correct order is: \"{correct}\". Subject first, then verb, then the rest.",
            f"ترتيب الكلمات مهم في الإنجليزية. الترتيب الصحيح: «{correct}». الفاعل أولاً، ثم الفعل، ثم الباقي.",
        ),
        "grammar": (
            f"Grammar tip: the right form is \"{correct}\". Watch the verb form carefully.",
            f"قاعدة: الصواب هو «{correct}». انتبه لصيغة الفعل.",
        ),
        "listening": (
            f"Listening tip: the line was \"{correct}\". Try listening again and focus on the stressed words.",
            f"تلميح استماع: الجملة هي «{correct}». استمع مرة أخرى وركّز على الكلمات المشدّدة.",
        ),
        "speaking": (
            f"Try saying \"{correct}\" out loud. Speak slowly the first time, then natural speed the second time.",
            f"حاول قول «{correct}» بصوت مرتفع. ببطء أولاً، ثم بسرعة طبيعية.",
        ),
        "translation": (
            f"A natural translation is \"{correct}\". Word-for-word translation is not always best.",
            f"الترجمة الطبيعية هي «{correct}». الترجمة الحرفية ليست دائماً الأفضل.",
        ),
    }
    return rules.get(mistake, (
        f"Not quite. The correct answer is \"{correct}\". Read it once, say it out loud, then move on.",
        f"ليست تماماً. الإجابة الصحيحة هي «{correct}». اقرأها مرة، قُلها بصوت مرتفع، ثم تابع.",
    ))


# ---------------------------------------------------------------------------
# Speaking feedback fallback (no STT).
# ---------------------------------------------------------------------------

def speaking_feedback(ctx: dict) -> tuple[str, str]:
    return (
        "Practice tip — repeat the sentence three times: once slow, once natural, once fast. "
        "Focus on word stress, not just words.",
        "نصيحة — كرر الجملة ثلاث مرات: ببطء، ثم بشكل طبيعي، ثم بسرعة. "
        "ركّز على نبر الكلمات، ليس الكلمات وحدها.",
    )


# ---------------------------------------------------------------------------
# End-of-Challenge advice fallback.
# ---------------------------------------------------------------------------

def end_advice(ctx: dict, session) -> tuple[str, str]:
    if session.wrong_count == 0:
        return (
            "Strong run! Try the next lesson to keep the pace.",
            "أداء ممتاز! تابع للدرس التالي لتحافظ على الإيقاع.",
        )
    if session.wrong_count <= 2:
        return (
            "Good effort. Review the questions you missed and try again tomorrow.",
            "أداء جيد. راجع الأسئلة التي أخطأت فيها وحاول غداً.",
        )
    return (
        "Take a short break. Then practice the same skill once more — small repetitions help.",
        "خذ استراحة قصيرة، ثم تدرّب على المهارة نفسها مرة أخرى — التكرار البسيط يساعد.",
    )


# ---------------------------------------------------------------------------
# Roleplay opener fallback — used to seed `start_short_roleplay` when AI off.
# ---------------------------------------------------------------------------

def roleplay_opener(ctx: dict) -> tuple[str, str]:
    return (
        "Let's practice. Imagine we just met. Say hello and tell me your name.",
        "هيا نتدرّب. تخيّل أننا التقينا للتو. ألقِ التحية وأخبرني باسمك.",
    )


# ---------------------------------------------------------------------------
# Mistake-explanation fallback (used by the Review screen).
# ---------------------------------------------------------------------------

def mistake_explanation(mistake) -> tuple[str, str]:
    return (
        f"Remember: the right answer here is \"{mistake.correct_answer or '(see answer)'}\". "
        f"Re-read the question slowly and try saying the answer out loud.",
        f"تذكّر: الإجابة الصحيحة هنا «{mistake.correct_answer or '(انظر الإجابة)'}». "
        f"اقرأ السؤال ببطء وحاول قول الإجابة بصوت مرتفع.",
    )
