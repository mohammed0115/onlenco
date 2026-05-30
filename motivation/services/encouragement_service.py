"""Encouragement message picker.

Returns a static, bilingual encouragement string per event type. Phase
5 keeps this dumb on purpose — no AI, no DB lookups; the catalog can
later be moved to MotivationMessage when copywriters want admin
control.

Tone rules:
  * Concise — one short sentence.
  * Respectful — works for adults AND kids; no baby-talk, no exclamation
    spam.
  * Encourages effort, not perfection.
"""
from __future__ import annotations

import hashlib
from typing import Optional


# Each event maps to a list of (en, ar) pairs. The picker picks
# deterministically based on a context key (e.g. session id) so two
# adjacent cards never show identical copy by accident.
MESSAGES: dict[str, list[tuple[str, str]]] = {
    "correct_answer": [
        ("Great job!",            "رائع جداً!"),
        ("Nice work!",            "أحسنت!"),
        ("Right on.",             "إجابة صحيحة."),
        ("Excellent!",            "ممتاز!"),
    ],
    "wrong_answer": [
        ("Good try. Mistakes help you learn.",
         "محاولة جيدة. الأخطاء تساعدك على التعلم."),
        ("Almost. Let's keep going.",
         "اقتربت. هيا نتابع."),
        ("Not quite — try the next one.",
         "ليست تماماً. جرب التالي."),
    ],
    "challenge_completed": [
        ("Nice work! You completed this challenge.",
         "عمل ممتاز! أكملت هذا التحدي."),
    ],
    "challenge_failed": [
        ("Good effort. Try again to strengthen this skill.",
         "محاولة جيدة. جرّب مرة أخرى لتقوية هذه المهارة."),
    ],
    "perfect_challenge": [
        ("Perfect! You answered everything correctly.",
         "ممتاز! أجبت على كل شيء بشكل صحيح."),
    ],
    "daily_goal_completed": [
        ("You reached your daily goal!",
         "حققت هدفك اليومي!"),
    ],
    "streak_continued": [
        ("Your streak continues. Keep it up.",
         "سلسلتك مستمرة. واصل التقدم."),
    ],
    "badge_awarded": [
        ("New badge unlocked.",
         "حصلت على شارة جديدة."),
    ],
    "comeback": [
        ("Welcome back. Good to see you again.",
         "أهلاً بعودتك. سعيدون برؤيتك مجدداً."),
    ],
    "low_hearts": [
        ("Take your time on the next one.",
         "خذ وقتك في السؤال التالي."),
    ],
    "first_lesson": [
        ("Your first lesson — well done.",
         "أول درس لك — أحسنت."),
    ],
}


def get_message(
    event_type: str,
    language: str = "en",
    context: Optional[dict] = None,
) -> str:
    """Return one bilingual-pair string for `event_type`.

    `context` is hashed to pick a stable variant — passing a session pk
    makes the same session show the same message on refresh.
    """
    pool = MESSAGES.get(event_type)
    if not pool:
        return ""
    # Deterministic pick within the pool.
    seed = ""
    if context:
        seed = "|".join(f"{k}={v}" for k, v in sorted(context.items()))
    idx = int(hashlib.md5(seed.encode("utf-8")).hexdigest(), 16) % len(pool)
    en, ar = pool[idx]
    return ar if (language or "en").startswith("ar") else en


def get_bilingual(
    event_type: str, context: Optional[dict] = None,
) -> tuple[str, str]:
    """Return both EN + AR — useful when the caller already loads both."""
    pool = MESSAGES.get(event_type) or [("", "")]
    seed = ""
    if context:
        seed = "|".join(f"{k}={v}" for k, v in sorted(context.items()))
    idx = int(hashlib.md5(seed.encode("utf-8")).hexdigest(), 16) % len(pool)
    return pool[idx]
