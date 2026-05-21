"""Text humanisation / speech sanitisation layer.

Single point of truth for cleaning anything that might be shown to a
student in the UI or read aloud by TTS. Use it before:
    - tutor / TTS playback
    - notification subject lookup
    - motivation message rendering
    - placement feedback display
    - dashboard labels generated from enums
    - email subject/body generated from event names

Public surface:
    humanize_text(text, language="en", mode="display")
    humanize_for_speech(text, language="en")
    humanize_event_name(event_type, language="en")
    humanize_field_name(field_name, language="en")

The functions are intentionally tolerant: bad input returns a safe
fallback rather than raising.
"""
from __future__ import annotations

import re
from typing import Optional

# ---------------------------------------------------------------------------
# Domain glossaries
#
# These are the only place in the codebase where we map raw technical names
# to user-facing copy. Add new event types / fields here, NOT in views or
# templates. Keys are always lower-case snake_case.
# ---------------------------------------------------------------------------

EVENT_NAMES_EN = {
    # student events
    "user_registered":              "Welcome to Onlenco",
    "email_verification":           "Confirm your email",
    "password_reset":               "Reset your password",
    "placement_completed":          "Placement test complete",
    "weakness_detected":            "New learning focus detected",
    "exercises_generated":          "New practice exercises are ready",
    "lesson_completed":             "Lesson complete",
    "weekly_assessment_available":  "Weekly assessment is available",
    "weekly_assessment_result":     "Your weekly assessment results",
    "level_improved":               "You leveled up",
    "subscription_expiring":        "Your subscription is ending soon",
    "payment_submitted":            "Payment received",
    "payment_approved":             "Payment approved",
    "payment_rejected":             "Payment needs attention",
    "inactive_student_reminder":    "We miss you",
    # admin events
    "new_student_registered":       "New student registered",
    "new_payment_pending":          "New payment pending review",
    "ai_usage_high":                "AI usage alert",
    "ai_failure":                   "AI service alert",
    "at_risk_student":              "At-risk student",
    "daily_admin_summary":          "Daily summary",
    "weekly_admin_summary":         "Weekly summary",
    # motivation events
    "motivation_message_generated": "A note for you",
    "achievement_unlocked":         "Achievement unlocked",
    "badge_earned":                 "New badge earned",
    "xp_awarded":                   "XP awarded",
    "streak_milestone":             "Streak milestone",
    "comeback_reminder":            "We miss you",
    "weekly_motivation_summary":    "Your week on Onlenco",
}

EVENT_NAMES_AR = {
    "user_registered":              "أهلاً بك في Onlenco",
    "email_verification":           "تأكيد البريد الإلكتروني",
    "password_reset":               "إعادة تعيين كلمة المرور",
    "placement_completed":          "اكتمل اختبار تحديد المستوى",
    "weakness_detected":            "تم تحديد نقطة تحتاج إلى تدريب",
    "exercises_generated":          "تم تجهيز تمارين جديدة لك",
    "lesson_completed":             "اكتمل الدرس",
    "weekly_assessment_available":  "الاختبار الأسبوعي متاح الآن",
    "weekly_assessment_result":     "نتائج اختبارك الأسبوعي",
    "level_improved":               "تقدمت إلى مستوى أعلى",
    "subscription_expiring":        "اشتراكك يقترب من الانتهاء",
    "payment_submitted":            "تم استلام الدفع",
    "payment_approved":             "تم قبول الدفع",
    "payment_rejected":             "الدفع يحتاج إلى مراجعة",
    "inactive_student_reminder":    "نفتقدك",
    "new_student_registered":       "تسجيل طالب جديد",
    "new_payment_pending":          "دفعة جديدة بانتظار المراجعة",
    "ai_usage_high":                "تنبيه استخدام الذكاء الاصطناعي",
    "ai_failure":                   "تنبيه خدمة الذكاء الاصطناعي",
    "at_risk_student":              "طالب يحتاج إلى متابعة",
    "daily_admin_summary":          "الملخص اليومي",
    "weekly_admin_summary":         "الملخص الأسبوعي",
    "motivation_message_generated": "رسالة لك",
    "achievement_unlocked":         "تم فتح إنجاز",
    "badge_earned":                 "حصلت على شارة جديدة",
    "xp_awarded":                   "نقاط XP جديدة",
    "streak_milestone":             "إنجاز السلسلة",
    "comeback_reminder":            "نفتقدك",
    "weekly_motivation_summary":    "ملخص أسبوعك على Onlenco",
}

FIELD_NAMES_EN = {
    "cefr_level":         "English level",
    "current_cefr_level": "English level",
    "theta_score":        "learning ability score",
    "skill_mastery":      "skill progress",
    "user_weakness":      "learning focus area",
    "adaptive_exercise":  "personalized exercise",
    "exercise_attempt":   "exercise attempt",
    "learning_recommendation": "learning suggestion",
    "weekly_assessment":  "weekly assessment",
    "lesson_progress":    "lesson progress",
    "speaking_minutes":   "speaking minutes",
    "ai_chat_minutes":    "AI tutor minutes",
    "words_read":         "words read",
    "lessons_completed":  "lessons completed",
    "questions_answered": "questions answered",
    "quiz_accuracy":      "quiz accuracy",
    "current_streak_days": "current streak",
    "xp_earned":          "XP earned",
    "vocabulary_words_learned": "new vocabulary",
    "writing_attempts":   "writing attempts",
    # Exercise / daily-plan payload keys that can leak into TTS text.
    "user_answer":        "your answer",
    "correct_answer":     "the correct answer",
    "daily_learning_plan": "today's learning plan",
}

FIELD_NAMES_AR = {
    "cefr_level":         "مستوى اللغة الإنجليزية",
    "current_cefr_level": "مستوى اللغة الإنجليزية",
    "theta_score":        "مؤشر مستوى التعلم",
    "skill_mastery":      "تقدم المهارة",
    "user_weakness":      "نقطة تحتاج إلى تحسين",
    "adaptive_exercise":  "تمرين مخصص",
    "exercise_attempt":   "محاولة تمرين",
    "learning_recommendation": "اقتراح تعلم",
    "weekly_assessment":  "الاختبار الأسبوعي",
    "lesson_progress":    "تقدم الدرس",
    "speaking_minutes":   "دقائق تحدث",
    "ai_chat_minutes":    "دقائق المعلم الذكي",
    "words_read":         "كلمات مقروءة",
    "lessons_completed":  "الدروس المكتملة",
    "questions_answered": "الأسئلة المجابة",
    "quiz_accuracy":      "دقة الإجابات",
    "current_streak_days": "السلسلة الحالية",
    "xp_earned":          "نقاط XP المكتسبة",
    "vocabulary_words_learned": "كلمات جديدة",
    "writing_attempts":   "محاولات الكتابة",
    # Exercise / daily-plan payload keys that can leak into TTS text.
    "user_answer":        "إجابة الطالب",
    "correct_answer":     "الإجابة الصحيحة",
    "daily_learning_plan": "خطة اليوم",
}

# Friendly fallbacks when a token can't be safely humanised.
SAFE_FALLBACK_EN = "Here is an update from Onlenco."
SAFE_FALLBACK_AR = "لديك تحديث من Onlenco."


def _merged_event_glossary(language: str) -> dict:
    """Return the event-name glossary, optionally merged with project-level
    extensions from `settings.TEXT_HUMANIZER_EVENT_NAMES_EN/AR`.

    This lets a deployment add new event types without editing this file.
    """
    base = EVENT_NAMES_AR if language == "ar" else EVENT_NAMES_EN
    try:
        from django.conf import settings
        extra_attr = "TEXT_HUMANIZER_EVENT_NAMES_AR" if language == "ar" else "TEXT_HUMANIZER_EVENT_NAMES_EN"
        extra = getattr(settings, extra_attr, None) or {}
    except Exception:
        extra = {}
    if not extra:
        return base
    merged = dict(base)
    for k, v in extra.items():
        if isinstance(k, str) and isinstance(v, str):
            merged[k.strip().lower()] = v
    return merged


def _merged_field_glossary(language: str) -> dict:
    """Same idea for field-name overrides via settings."""
    base = FIELD_NAMES_AR if language == "ar" else FIELD_NAMES_EN
    try:
        from django.conf import settings
        extra_attr = "TEXT_HUMANIZER_FIELD_NAMES_AR" if language == "ar" else "TEXT_HUMANIZER_FIELD_NAMES_EN"
        extra = getattr(settings, extra_attr, None) or {}
    except Exception:
        extra = {}
    if not extra:
        return base
    merged = dict(base)
    for k, v in extra.items():
        if isinstance(k, str) and isinstance(v, str):
            merged[k.strip().lower()] = v
    return merged

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

# Match: snake_case word(s) of length >= 2 segments, e.g. "snake_case_thing".
_SNAKE_RE = re.compile(r"\b([a-z][a-z0-9]*(?:_[a-z0-9]+)+)\b")
# Match: camelCase or PascalCase tokens with at least one inner capital.
_CAMEL_RE = re.compile(r"\b([a-z][a-z0-9]+(?:[A-Z][a-z0-9]+)+|[A-Z][a-z0-9]+(?:[A-Z][a-z0-9]+)+)\b")
# Match: unresolved Django/Jinja-ish placeholders like {{ var }} or {{var.x}}.
_PLACEHOLDER_RE = re.compile(r"\{\{\s*[^{}]+\s*\}\}|\{%\s*[^{}]+\s*%\}")
# Three or more consecutive blanks/dashes.
_LONG_DASH_RE = re.compile(r"-{2,}")
# Dashes between letters (snake-style) → space.
_DASH_BETWEEN_WORDS = re.compile(r"(?<=\w)-(?=\w)")
# Any run of "blank" markers (typed or rendered placeholders).
_LITERAL_BLANK_RE = re.compile(r"(?:^|[\s\-_]+)(?:blank|null|none|undefined)(?:[\s\-_]+(?:blank|null|none|undefined))*", re.IGNORECASE)
# Markdown-y artefacts we don't want spoken.
_MD_FENCE_RE = re.compile(r"```[\s\S]*?```")
_MD_INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
_MD_BOLD_RE = re.compile(r"\*\*([^*\n]+)\*\*")
# Only treat asterisks as italic. Underscores are excluded because they
# clash with snake_case identifiers we explicitly want to humanise.
_MD_ITALIC_RE = re.compile(r"(?<!\*)\*(?!\*)([^*\n]+?)\*(?!\*)")
# URLs + file paths to drop in speech mode.
_URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
_FILE_PATH_RE = re.compile(r"(?:^|\s)(?:/|[A-Za-z]:\\)[^\s]+")
# JSON/dict-ish blob ({"k": "v", ...}) — drop in speech mode.
_JSON_BLOB_RE = re.compile(r"\{[^{}]*\}")
# Long opaque IDs (UUIDs, hex blobs >= 24 chars).
_OPAQUE_ID_RE = re.compile(r"\b[a-f0-9]{8,}-[a-f0-9-]+|\b[A-Za-z0-9]{24,}\b")
# Multiple whitespace.
_WS_RE = re.compile(r"\s+")


def _split_snake(token: str) -> str:
    return token.replace("_", " ").strip()


def _split_camel(token: str) -> str:
    # Insert a space before every internal capital, lowercase the rest.
    out = re.sub(r"(?<=[a-z0-9])([A-Z])", r" \1", token)
    return out.strip()


def _humanise_snake_case_in(text: str) -> str:
    return _SNAKE_RE.sub(lambda m: _split_snake(m.group(1)), text)


def _humanise_camel_case_in(text: str) -> str:
    return _CAMEL_RE.sub(lambda m: _split_camel(m.group(1)), text)


def _strip_unresolved_placeholders(text: str) -> str:
    return _PLACEHOLDER_RE.sub("", text)


def _strip_markdown(text: str) -> str:
    text = _MD_FENCE_RE.sub("", text)
    text = _MD_INLINE_CODE_RE.sub("", text)
    text = _MD_BOLD_RE.sub(r"\1", text)
    text = _MD_ITALIC_RE.sub(r"\1", text)
    return text


def _collapse_whitespace(text: str) -> str:
    text = _LONG_DASH_RE.sub(" ", text)
    text = _DASH_BETWEEN_WORDS.sub(" ", text)
    text = _WS_RE.sub(" ", text).strip()
    # If we end up with only structural punctuation / underscores, treat
    # that as empty so the caller falls back to a safe message. (Note: we
    # exclude `_` from the meaningfulness check because it is in `\w`.)
    if text and not re.search(r"[A-Za-z0-9؀-ۿ]", text):
        return ""
    return text


# ---------------------------------------------------------------------------
# Speech-only transforms
# ---------------------------------------------------------------------------

# CEFR letter-only tokens that should be expanded for clearer TTS.
_CEFR_RE = re.compile(r"\b([ABC])([0-3])\b")


def _cefr_for_speech(text: str, language: str) -> str:
    if language == "ar":
        # Arabic readers want the level kept verbatim ("المستوى A1").
        return _CEFR_RE.sub(lambda m: f"المستوى {m.group(1)}{m.group(2)}", text)
    digit_words = {"0": "zero", "1": "one", "2": "two", "3": "three"}
    return _CEFR_RE.sub(
        lambda m: f"{m.group(1)} {digit_words.get(m.group(2), m.group(2))} level",
        text,
    )


def _percent_for_speech(text: str, language: str) -> str:
    if language == "ar":
        return re.sub(r"(\d+)\s*%", lambda m: f"{m.group(1)} بالمئة", text)
    return re.sub(r"(\d+)\s*%", lambda m: f"{m.group(1)} percent", text)


def _drop_unspeakable(text: str) -> str:
    """Strip URLs, file paths, JSON blobs, opaque IDs."""
    text = _URL_RE.sub("", text)
    text = _FILE_PATH_RE.sub(" ", text)
    text = _JSON_BLOB_RE.sub("", text)
    text = _OPAQUE_ID_RE.sub("", text)
    return text


_SPEECH_PAREN_HINT_RE = re.compile(r"\([^()]*\)|\[[^\[\]]*\]")
_SPEECH_UNDERSCORE_RE = re.compile(r"_{1,}")
_SPEECH_ZERO_WIDTH_RE = re.compile(r"[\u200B-\u200F\u202A-\u202E\u2060-\u206F\uFEFF]")
_SPEECH_HTML_TAG_RE = re.compile(r"<[^>]+>")
_SPEECH_HTML_ENTITY_RE = re.compile(r"&(?:[a-zA-Z]+|#\d+|#x[0-9a-fA-F]+);")
_SPEECH_PUNCT_WORD_RE = re.compile(
    r"\b(?:"
    r"u\s*a|ua|"
    r"new\s*line|newline|"
    r"comma|commas|"
    r"underscore|underscores|"
    r"dash|dashes|hyphen|hyphens|minus\s+sign|minus|"
    r"slash|slashes|backslash|back\s+slash|"
    r"colon|colons|semicolon|semicolons|"
    r"period|periods|full\s+stop|full\s+stops|question\s+mark|exclamation\s+mark|"
    r"dot|dots|"
    r"quote|quotes|quotation|quotations|open\s+quote|close\s+quote|"
    r"apostrophe|apostrophes|"
    r"bracket|brackets|open\s+bracket|close\s+bracket|"
    r"parenthesis|parentheses|open\s+parenthesis|close\s+parenthesis|"
    r"asterisk|asterisks|star|stars|"
    r"hash|hashtag|at\s+sign|ampersand|equals|equal\s+sign|plus|plus\s+sign|"
    r"pipe|vertical\s+bar|tilde|backtick"
    r")\b",
    re.IGNORECASE,
)
_SPEECH_ODD_SYMBOL_RE = re.compile(
    r"[#@\$€£¥₹₿^&*+=<>|~`\\/{}\[\]"
    r"•·…§©®™✓✔✕✖✗✘→←↑↓↔⇒⇐⇔★☆♥♦♣♠■□▪▫▲▼◆◇●○◦°]+"
)


def _strip_speech_artifacts(text: str) -> str:
    """Remove tokens that TTS engines read as literal noise.

    These show up in generated exercises and AI output as fill-in blanks
    (``____``), punctuation labels (``comma``), or internal prefixes
    (``UA``). They are useful metadata on screen, but should never be
    spoken to the learner.
    """
    text = _SPEECH_ZERO_WIDTH_RE.sub("", text)
    text = _SPEECH_HTML_TAG_RE.sub(" ", text)
    text = _SPEECH_HTML_ENTITY_RE.sub(" ", text)
    text = _SPEECH_PAREN_HINT_RE.sub(" ", text)
    text = _SPEECH_UNDERSCORE_RE.sub(" ", text)
    text = _SPEECH_PUNCT_WORD_RE.sub(" ", text)
    text = _SPEECH_ODD_SYMBOL_RE.sub(" ", text)
    # Remove punctuation that becomes orphaned after stripping labels/symbols.
    text = re.sub(r"\s+([,.;:!?؟،])", r"\1", text)
    text = re.sub(r"(^|[\s])[,.;:!?؟،]+(?=\s|$)", " ", text)
    return text


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def humanize_event_name(event_type: str, language: str = "en") -> str:
    """Map an event_type key to a user-facing label.

    Falls back to a snake_case → sentence-case transformation when the
    glossary has no entry, then to the safe fallback when even that
    yields nothing useful.
    """
    if not event_type:
        return SAFE_FALLBACK_AR if language == "ar" else SAFE_FALLBACK_EN
    key = str(event_type).strip().lower()
    glossary = _merged_event_glossary(language)
    if key in glossary:
        return glossary[key]
    cleaned = _split_snake(key).strip()
    if not cleaned:
        return SAFE_FALLBACK_AR if language == "ar" else SAFE_FALLBACK_EN
    return cleaned[:1].upper() + cleaned[1:] if language != "ar" else cleaned


def humanize_field_name(field_name: str, language: str = "en") -> str:
    """Map a model field / payload key to a user-facing label."""
    if not field_name:
        return ""
    key = str(field_name).strip().lower()
    glossary = _merged_field_glossary(language)
    if key in glossary:
        return glossary[key]
    return _split_snake(key)


def humanize_text(
    text: Optional[str],
    language: str = "en",
    mode: str = "display",
) -> str:
    """General cleanup. `mode` is "display" (preserves punctuation) or
    "speech" (also strips URLs, paths, JSON, expands CEFR + percentages).

    Always returns a string. Never raises.
    """
    if text is None:
        return ""
    if not isinstance(text, str):
        try:
            text = str(text)
        except Exception:
            return ""

    # Detect "lone snake_case identifier" so we can title-case the result
    # at the end — that keeps `user_profile_updated` → `User profile updated`
    # while leaving in-sentence casing untouched.
    is_lone_token = (
        text.strip() != ""
        and not any(ch.isspace() for ch in text.strip())
        and re.fullmatch(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)+", text.strip()) is not None
    )

    out = text

    # 1. Drop unresolved Django/Jinja placeholders.
    out = _strip_unresolved_placeholders(out)
    # 2. Drop literal "blank/null/undefined" runs.
    out = _LITERAL_BLANK_RE.sub(" ", out)
    # 2b. Strip hard-banned identifiers ("UA_user_answer", "DB_*", …)
    #     BEFORE the snake_case humaniser would otherwise read them.
    out = _strip_hard_banned(out)

    # 3. Replace known field tokens (cefr_level → English level, …). Pull
    #    the merged glossary so settings-level extensions are honoured.
    fields_glossary = _merged_field_glossary(language)
    for k, v in fields_glossary.items():
        out = re.sub(rf"\b{re.escape(k)}\b", v, out)

    # 4. Replace known event tokens too — same idea, different glossary.
    events_glossary = _merged_event_glossary(language)
    for k, v in events_glossary.items():
        out = re.sub(rf"\b{re.escape(k)}\b", v, out)

    # 5. Generic snake_case + camelCase → words.
    out = _humanise_snake_case_in(out)
    out = _humanise_camel_case_in(out)

    if mode == "speech":
        # Markdown should never be spoken — fences contain code, inline
        # code is unintelligible. Display mode keeps formatting because a
        # tutor reply may reasonably contain `**bold**` or backticks.
        out = _strip_markdown(out)
        out = _drop_unspeakable(out)
        out = _strip_speech_artifacts(out)
        out = _percent_for_speech(out, language)
        out = _cefr_for_speech(out, language)

    out = _collapse_whitespace(out)

    if not out:
        return SAFE_FALLBACK_AR if language == "ar" else SAFE_FALLBACK_EN

    # If the original input was a single snake_case identifier (e.g.
    # "user_profile_updated"), the result is a short event-style phrase
    # that reads better in sentence-case. Don't touch sentences.
    if is_lone_token and language != "ar" and out and out[0].islower():
        out = out[0].upper() + out[1:]
    return out


def humanize_for_speech(text: Optional[str], language: str = "en") -> str:
    """Convenience wrapper: `humanize_text(..., mode='speech')`.

    This is the ONLY function any TTS path should call. Run every string
    through it before handing it to `speechSynthesis`, an OpenAI TTS
    request, or an audio player — never pass raw text to a voice engine.
    """
    return humanize_text(text, language=language, mode="speech")


def remove_tts_noise_tokens(text: Optional[str]) -> str:
    """Strip TTS noise tokens only — no glossary, no CEFR/percent expansion.

    Removes the artefacts a voice engine would otherwise read as literal
    noise: fill-in-the-blank underscores (``_``, ``__``, ``___``), ``UA``
    / punctuation labels, ``blank``/``null``/``undefined`` runs, hard-banned
    technical prefixes (``UA_…``, ``DB_…``), unresolved ``{{ }}`` /
    ``{% %}`` placeholders, and decorative symbols.

    Use when you only need to scrub noise (e.g. a string that is already
    human copy). For full humanisation use `humanize_for_speech`.
    Always returns a string. Never raises.
    """
    if text is None:
        return ""
    if not isinstance(text, str):
        try:
            text = str(text)
        except Exception:
            return ""
    out = _strip_unresolved_placeholders(text)
    out = _LITERAL_BLANK_RE.sub(" ", out)
    out = _strip_hard_banned(out)
    out = _strip_speech_artifacts(out)
    return _collapse_whitespace(out)


def humanize_technical_tokens(text: Optional[str], language: str = "ar") -> str:
    """Replace technical identifiers with human-readable copy.

    Maps known field/event keys (``cefr_level`` → "English level" /
    "مستوى اللغة الإنجليزية", ``weekly_assessment_available`` → …) and
    splits leftover ``snake_case`` / ``camelCase`` identifiers into words.
    Does NOT do the speech-only scrubbing — pair it with
    `remove_tts_noise_tokens` or just call `humanize_for_speech`, which
    does both. Always returns a string. Never raises.
    """
    if text is None:
        return ""
    if not isinstance(text, str):
        try:
            text = str(text)
        except Exception:
            return ""
    out = text
    for k, v in _merged_field_glossary(language).items():
        out = re.sub(rf"\b{re.escape(k)}\b", v, out)
    for k, v in _merged_event_glossary(language).items():
        out = re.sub(rf"\b{re.escape(k)}\b", v, out)
    out = _humanise_snake_case_in(out)
    out = _humanise_camel_case_in(out)
    return _collapse_whitespace(out)


# ---------------------------------------------------------------------------
# Mixed Arabic / English text
# ---------------------------------------------------------------------------

# Latin word (letters + optional inner digit/dot/dash/underscore).
_LATIN_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9._-]{0,40}")
# A run of Arabic words (Arabic letters + whitespace).
_ARABIC_RUN_RE = re.compile(
    r"[؀-ۿݐ-ݿࢠ-ࣿﭐ-﷿ﹰ-﻿]+"
    r"(?:\s+[؀-ۿݐ-ݿࢠ-ࣿﭐ-﷿ﹰ-﻿]+)*"
)


def sanitize_mixed_language_text(
    text: Optional[str],
    primary_language: str = "ar",
    *,
    mode: str = "display",
) -> str:
    """Wrap minority-language runs in HTML so RTL/LTR rendering is correct.

    Use this for any user-facing string that may contain both Arabic and
    English (e.g. "مستواك A1 improved by 12%"). In `display` mode the
    function wraps each minority run in ``<bdi dir="ltr">…</bdi>`` (or
    ``rtl`` when the primary is English), so the browser stops
    bidirectional reordering at the boundary. In `speech` mode the
    function falls through to ``humanize_for_speech`` because `<bdi>`
    wrappers are unspeakable HTML.

    Always returns a string. Never raises.
    """
    if text is None:
        return ""
    if not isinstance(text, str):
        try:
            text = str(text)
        except Exception:
            return ""
    if mode == "speech":
        return humanize_for_speech(text, language=primary_language)

    primary = (primary_language or "ar").lower()
    if primary == "ar":
        return _LATIN_WORD_RE.sub(
            lambda m: f'<bdi dir="ltr">{m.group(0)}</bdi>',
            text,
        )
    # primary == "en" — wrap any Arabic run in <bdi dir="rtl">.
    return _ARABIC_RUN_RE.sub(
        lambda m: f'<bdi dir="rtl">{m.group(0)}</bdi>',
        text,
    )


# ---------------------------------------------------------------------------
# Hard safety guards for raw technical identifiers
# ---------------------------------------------------------------------------

# Common technical prefixes that must NEVER reach the user, regardless
# of casing. Examples: "UA_user_answer", "DB_user_profile_id".
_HARD_BANNED_PREFIXES = (
    "UA_", "DB_", "ID_", "PK_", "FK_", "ENUM_", "CTX_", "SQL_",
)
_HARD_BANNED_RES = tuple(
    re.compile(rf"\b{re.escape(prefix)}[A-Za-z0-9_]+\b", re.IGNORECASE)
    for prefix in _HARD_BANNED_PREFIXES
)


def _strip_hard_banned(text: str) -> str:
    """Remove tokens beginning with one of `_HARD_BANNED_PREFIXES`."""
    if not text:
        return text
    for pattern in _HARD_BANNED_RES:
        text = pattern.sub(" ", text)
    return text
