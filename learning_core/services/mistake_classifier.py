"""Classify a wrong ChallengeAnswer into a StudentMistake.mistake_type.

Rule-based — looks at `question.question_type` first, falls back to
`unknown`. AI hooks can be layered on later without touching callers.
"""
from __future__ import annotations


# question_type → (mistake_type, severity)
TYPE_MAP: dict[str, tuple[str, str]] = {
    # ----- Tap / choice -----
    "tap_choice":           ("wrong_choice", "low"),
    "image_choice":         ("wrong_choice", "low"),
    "mini_story_choice":    ("wrong_choice", "medium"),
    "conversation_reply":   ("wrong_choice", "low"),
    "translate_to_arabic":  ("translation",  "medium"),

    # ----- Listening -----
    "listen_and_choose":    ("listening",    "medium"),
    "listen_and_type":      ("listening",    "high"),
    "sound_to_word":        ("listening",    "medium"),

    # ----- Vocabulary -----
    "picture_labeling":     ("spelling",     "medium"),
    "translate_to_english": ("translation",  "high"),

    # ----- Grammar -----
    "word_bank_sentence":   ("word_order",   "medium"),
    "fill_blank_card":      ("grammar",      "medium"),
    "table_sentence_builder": ("grammar",    "medium"),
    "question_transform":   ("grammar",      "high"),
    "mistake_correction":   ("grammar",      "high"),
    "frequency_scale":      ("grammar",      "low"),
    "match_pairs":          ("wrong_choice", "low"),

    # ----- Speaking placeholders -----
    "speak_this_sentence":  ("speaking",     "low"),
    "pronunciation_check":  ("speaking",     "low"),
    "ai_roleplay_prompt":   ("speaking",     "low"),

    # ----- Legacy types -----
    "multiple_choice":    ("wrong_choice", "low"),
    "fill_blank":         ("grammar",      "medium"),
    "correction":         ("grammar",      "high"),
    "sentence_ordering":  ("word_order",   "medium"),
    "translation":        ("translation",  "high"),
    "short_answer":       ("grammar",      "medium"),
    "speaking_prompt":    ("speaking",     "low"),
    "writing_prompt":     ("grammar",      "medium"),
}


def classify(question) -> tuple[str, str]:
    """Return (mistake_type, severity) for the given LessonQuestion."""
    qt = (getattr(question, "question_type", "") or "").strip()
    return TYPE_MAP.get(qt, ("unknown", "medium"))
