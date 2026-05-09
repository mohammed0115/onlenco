"""Generate bilingual MotivationMessage rows from snapshots/achievements.

Picks tone based on activity level + user preference, then renders a
title + body in EN or AR (matching the user's preferred_language).
"""
from __future__ import annotations

import random
from typing import Optional

from django.utils import timezone

from .. import constants as C
from ..models import (
    Achievement,
    LearnerActivitySnapshot,
    MotivationMessage,
    MotivationPreference,
    UserAchievement,
)


# ---------- tone selection ----------

def _user_language(user) -> str:
    prof = getattr(user, "profile", None)
    if prof and getattr(prof, "preferred_language", None) in ("ar", "en"):
        return prof.preferred_language
    return "en"


def _user_preference(user) -> MotivationPreference:
    pref, _ = MotivationPreference.objects.get_or_create(user=user)
    return pref


def select_tone(user, snap: Optional[LearnerActivitySnapshot]) -> str:
    pref = _user_preference(user)
    base = pref.preferred_tone or C.TONE_SUPPORTIVE

    if snap is None:
        return base
    inactive = snap.inactive_days or 0
    xp_today = (snap.metadata or {}).get("xp_awarded", 0)
    accuracy = snap.quiz_accuracy or 0

    if inactive >= C.TONE_FOR_INACTIVE_DAYS_MIN:
        return C.TONE_GENTLE
    if accuracy and accuracy < 50:
        return C.TONE_SUPPORTIVE
    if xp_today >= C.TONE_FOR_HIGH_ACTIVITY_XP:
        return C.TONE_ENERGETIC if base != C.TONE_PROFESSIONAL else C.TONE_PROFESSIONAL
    return base


# ---------- copy banks (EN + AR) ----------

ENCOURAGEMENT_TEMPLATES = {
    "en": {
        C.TONE_ENERGETIC: [
            "🔥 You crushed it today! Keep that energy going.",
            "💪 Strong session — that's how progress happens.",
            "Look at you go — every minute is paying off!",
        ],
        C.TONE_GENTLE: [
            "A small step today is still a step. Proud of you.",
            "Consistency beats intensity. You showed up — that matters.",
        ],
        C.TONE_SUPPORTIVE: [
            "Nice work. Your future self will thank you.",
            "Solid effort today. Tomorrow we go again.",
        ],
        C.TONE_CHALLENGING: [
            "Good — but I know you've got more in you. Push tomorrow.",
            "Don't settle. The next level needs another rep.",
        ],
        C.TONE_PROFESSIONAL: [
            "Productive session today. Continue at this pace.",
            "Steady progress recorded. Maintain the cadence.",
        ],
    },
    "ar": {
        C.TONE_ENERGETIC: [
            "🔥 أحسنت اليوم! حافظ على هذه الطاقة.",
            "💪 جلسة قوية — هكذا يحدث التقدم.",
            "كل دقيقة تستثمرها تؤتي ثمارها!",
        ],
        C.TONE_GENTLE: [
            "خطوة صغيرة اليوم تظل خطوة. فخور بك.",
            "الانتظام أهم من الشدّة. حضورك يكفي اليوم.",
        ],
        C.TONE_SUPPORTIVE: [
            "عمل جيد. مستقبلك سيشكرك.",
            "مجهود محترم اليوم. غداً نُكمل.",
        ],
        C.TONE_CHALLENGING: [
            "جيد — لكنك تستطيع أكثر. ادفع غداً.",
            "لا ترضَ بالقليل. المستوى التالي يحتاج جولة إضافية.",
        ],
        C.TONE_PROFESSIONAL: [
            "جلسة منتجة. واصل بنفس الإيقاع.",
            "تقدم منتظم مسجَّل. حافظ على الوتيرة.",
        ],
    },
}


COMEBACK_TEMPLATES = {
    "en": [
        "We miss you ✨ Just 10 minutes today rebuilds the habit.",
        "Welcome back — start with one short lesson and we'll go from there.",
        "Quick comeback session: a 3-minute drill is enough to break the silence.",
    ],
    "ar": [
        "نفتقدك ✨ عشر دقائق اليوم تعيد بناء العادة.",
        "أهلاً بعودتك — ابدأ بدرس قصير وسنُكمل معاً.",
        "جلسة عودة سريعة: 3 دقائق تكفي لكسر الانقطاع.",
    ],
}


STREAK_TEMPLATES = {
    "en": [
        "🔥 {days}-day streak — every day stacks up.",
        "{days} days strong. Don't break the chain!",
    ],
    "ar": [
        "🔥 سلسلة {days} يوماً — كل يوم يضاف لرحلتك.",
        "{days} أيام بدون انقطاع. لا تكسر السلسلة!",
    ],
}


WEEKLY_SUMMARY_OPENER = {
    "en": [
        "Your week, by the numbers — and what's next.",
        "Here's how this week went. Tiny gains add up.",
    ],
    "ar": [
        "أسبوعك بالأرقام — وما الخطوة التالية.",
        "هذا ملخّص أسبوعك. الإنجازات الصغيرة تتراكم.",
    ],
}


# ---------- public API ----------

def build_message(
    user,
    *,
    message_type: str,
    snap: Optional[LearnerActivitySnapshot] = None,
    achievement: Optional[Achievement] = None,
    related_activity: str = "",
    extra: Optional[dict] = None,
) -> MotivationMessage:
    lang = _user_language(user)
    tone = select_tone(user, snap)
    extra = extra or {}

    title, body = _render(message_type, lang, tone, snap, achievement, extra)

    msg = MotivationMessage.objects.create(
        user=user,
        message_type=message_type,
        title=title,
        message=body,
        language=lang,
        tone=tone,
        related_activity=related_activity,
        related_achievement=achievement,
        related_snapshot=snap,
        status=C.STATUS_GENERATED,
        sent_via=C.VIA_NONE,
        metadata=extra,
    )
    return msg


def _render(message_type, lang, tone, snap, achievement, extra):
    if message_type == C.MSG_ACHIEVEMENT and achievement is not None:
        title = (achievement.name_ar or achievement.name) if lang == "ar" else achievement.name
        desc = (achievement.description_ar or achievement.description) if lang == "ar" else achievement.description
        return title, desc or title

    if message_type == C.MSG_STREAK:
        days = (snap.current_streak_days if snap else extra.get("days", 0)) or 0
        body = random.choice(STREAK_TEMPLATES[lang]).format(days=days)
        title = ("🔥 سلسلة!" if lang == "ar" else "🔥 Streak!")
        return title, body

    if message_type == C.MSG_COMEBACK:
        title = ("نفتقدك" if lang == "ar" else "We miss you")
        return title, random.choice(COMEBACK_TEMPLATES[lang])

    if message_type == C.MSG_WEEKLY_SUMMARY:
        title = ("ملخص أسبوعك" if lang == "ar" else "Your week on Onlenco")
        return title, random.choice(WEEKLY_SUMMARY_OPENER[lang])

    if message_type == C.MSG_WARNING:
        title = ("لا تفقد سلسلتك" if lang == "ar" else "Don't lose your streak")
        body = (
            "أكمل تمريناً قصيراً اليوم لتحافظ على إيقاعك."
            if lang == "ar"
            else "Finish a short drill today to keep your rhythm."
        )
        return title, body

    if message_type == C.MSG_GOAL:
        title = ("هدف اليوم" if lang == "ar" else "Today's goal")
        body = (
            "حاول إكمال درس واحد + تمرين واحد قصير."
            if lang == "ar"
            else "Try to finish one lesson + one short drill."
        )
        return title, body

    if message_type == C.MSG_CHALLENGE:
        title = ("تحدي اليوم" if lang == "ar" else "Today's challenge")
        body = (
            "حقق دقة 80%+ على 10 أسئلة جديدة."
            if lang == "ar"
            else "Hit 80%+ accuracy on 10 fresh questions."
        )
        return title, body

    # default: encouragement
    bank = ENCOURAGEMENT_TEMPLATES[lang].get(tone) or ENCOURAGEMENT_TEMPLATES[lang][C.TONE_SUPPORTIVE]
    body = random.choice(bank)
    title = ("استمر" if lang == "ar" else "Keep going")
    return title, body
