"""Central registry for every question_type the Quiz/Challenge engine knows.

One source of truth used by:
  * `challenge_composer` — to filter the question sequence
  * `challenge_grading`  — to dispatch to the right grader
  * Challenge UI         — to pick the partial template
  * Teacher / admin      — to know which metadata fields are required
  * Tests                — to assert that every type renders + grades

Each entry is a `TypeSpec` dict with the keys below. Anything not in
the registry is treated as `unsupported`.

  label                  Human label (also rendered as Challenge kicker)
  skill                  list[str] — one or more of: vocabulary / grammar /
                         listening / speaking / reading / writing
  requires_metadata      bool — registry-level hint for teacher validation
  required_metadata_keys list[str] — names checked at validation time
  supports_auto_grading  bool — False means the grader returns a neutral
                         "noted" result (used by speak_* / ai_roleplay_*)
  supports_challenge     bool — False keeps the type out of Challenges
                         (but it can still appear in the Classic quiz)
  renderer               relative template path inside
                         `templates/courses/question_renderers/`
  grader                 dotted key for `question_graders.GRADERS`
  placeholder            bool — True means the renderer shows a "not
                         playable yet" card and the grader returns
                         neutral

Naming: keep keys URL-safe lowercase snake — they become CSS class
modifiers in the renderers.
"""
from __future__ import annotations

from typing import Any


TypeSpec = dict[str, Any]


# ---------------------------------------------------------------------------
# 20 launch types — Phase 3 deliverable.
# ---------------------------------------------------------------------------
QUESTION_TYPE_REGISTRY: dict[str, TypeSpec] = {

    # --- 1. Tap choice — fast MCQ with big tiles -------------------------
    "tap_choice": {
        "label_en": "Pick the right answer",
        "label_ar": "اختر الإجابة الصحيحة",
        "skill": ["vocabulary", "grammar"],
        "requires_metadata": True,
        "required_metadata_keys": ["options", "correct_option_id"],
        "supports_auto_grading": True,
        "supports_challenge": True,
        "renderer": "tap_choice.html",
        "grader": "tap_choice",
        "placeholder": False,
    },

    # --- 2. Image choice — pick a picture --------------------------------
    "image_choice": {
        "label_en": "Pick the right picture",
        "label_ar": "اختر الصورة الصحيحة",
        "skill": ["vocabulary"],
        "requires_metadata": True,
        "required_metadata_keys": ["options", "correct_option_id"],
        "supports_auto_grading": True,
        "supports_challenge": True,
        "renderer": "image_choice.html",
        "grader": "tap_choice",   # same matching logic
        "placeholder": False,
    },

    # --- 3. Listen and choose --------------------------------------------
    "listen_and_choose": {
        "label_en": "Listen and pick the answer",
        "label_ar": "استمع ثم اختر",
        "skill": ["listening"],
        "requires_metadata": True,
        "required_metadata_keys": ["audio_script", "options", "correct_option_id"],
        "supports_auto_grading": True,
        "supports_challenge": True,
        "renderer": "listen_and_choose.html",
        "grader": "tap_choice",
        "placeholder": False,
    },

    # --- 4. Listen and type ----------------------------------------------
    "listen_and_type": {
        "label_en": "Listen and type",
        "label_ar": "استمع ثم اكتب",
        "skill": ["listening", "writing"],
        "requires_metadata": True,
        "required_metadata_keys": ["audio_script", "correct_answer"],
        "supports_auto_grading": True,
        "supports_challenge": True,
        "renderer": "listen_and_type.html",
        "grader": "listen_and_type",
        "placeholder": False,
    },

    # --- 5. Sound to word ------------------------------------------------
    "sound_to_word": {
        "label_en": "Pick the word you heard",
        "label_ar": "اختر الكلمة التي سمعتها",
        "skill": ["listening"],
        "requires_metadata": True,
        "required_metadata_keys": ["audio_script", "options", "correct_option_id"],
        "supports_auto_grading": True,
        "supports_challenge": True,
        "renderer": "sound_to_word.html",
        "grader": "tap_choice",
        "placeholder": False,
    },

    # --- 6. Picture labeling ---------------------------------------------
    "picture_labeling": {
        "label_en": "Name what you see",
        "label_ar": "سمِّ ما تراه",
        "skill": ["vocabulary"],
        "requires_metadata": True,
        "required_metadata_keys": ["image_prompt", "accepted_answers"],
        "supports_auto_grading": True,
        "supports_challenge": True,
        "renderer": "picture_labeling.html",
        "grader": "accepted_answers",
        "placeholder": False,
    },

    # --- 7. Mini story choice --------------------------------------------
    "mini_story_choice": {
        "label_en": "Read, then answer",
        "label_ar": "اقرأ ثم أجب",
        "skill": ["reading"],
        "requires_metadata": True,
        "required_metadata_keys": ["story", "options", "correct_option_id"],
        "supports_auto_grading": True,
        "supports_challenge": True,
        "renderer": "mini_story_choice.html",
        "grader": "tap_choice",
        "placeholder": False,
    },

    # --- 8. Word bank sentence -------------------------------------------
    "word_bank_sentence": {
        "label_en": "Build the sentence",
        "label_ar": "ابنِ الجملة",
        "skill": ["grammar"],
        "requires_metadata": True,
        "required_metadata_keys": ["word_bank", "correct_order"],
        "supports_auto_grading": True,
        "supports_challenge": True,
        "renderer": "word_bank_sentence.html",
        "grader": "word_bank_sentence",
        "placeholder": False,
    },

    # --- 9. Match pairs --------------------------------------------------
    "match_pairs": {
        "label_en": "Match the pairs",
        "label_ar": "طابق الأزواج",
        "skill": ["vocabulary"],
        "requires_metadata": True,
        "required_metadata_keys": ["pairs"],
        "supports_auto_grading": True,
        "supports_challenge": True,
        "renderer": "match_pairs.html",
        "grader": "match_pairs",
        "placeholder": False,
    },

    # --- 10. Fill blank card ---------------------------------------------
    "fill_blank_card": {
        "label_en": "Fill the blank",
        "label_ar": "املأ الفراغ",
        "skill": ["grammar", "vocabulary"],
        "requires_metadata": False,   # uses correct_answer column
        "required_metadata_keys": [],
        "supports_auto_grading": True,
        "supports_challenge": True,
        "renderer": "fill_blank_card.html",
        "grader": "normalize_equality",
        "placeholder": False,
    },

    # --- 11. Conversation reply ------------------------------------------
    "conversation_reply": {
        "label_en": "Pick the natural reply",
        "label_ar": "اختر الرد المناسب",
        "skill": ["reading", "vocabulary"],
        "requires_metadata": True,
        "required_metadata_keys": ["dialogue", "options", "correct_option_id"],
        "supports_auto_grading": True,
        "supports_challenge": True,
        "renderer": "conversation_reply.html",
        "grader": "tap_choice",
        "placeholder": False,
    },

    # --- 12. Frequency scale ---------------------------------------------
    "frequency_scale": {
        "label_en": "Place the word on the scale",
        "label_ar": "ضع الكلمة على المقياس",
        "skill": ["grammar"],
        "requires_metadata": True,
        "required_metadata_keys": ["scale", "target"],
        "supports_auto_grading": True,
        "supports_challenge": True,
        "renderer": "frequency_scale.html",
        "grader": "frequency_scale",
        "placeholder": False,
    },

    # --- 13. Table sentence builder --------------------------------------
    "table_sentence_builder": {
        "label_en": "Build sentences from the table",
        "label_ar": "كوّن جملاً من الجدول",
        "skill": ["grammar"],
        "requires_metadata": True,
        "required_metadata_keys": ["columns"],
        "supports_auto_grading": True,
        "supports_challenge": True,
        "renderer": "table_sentence_builder.html",
        "grader": "table_sentence_builder",
        "placeholder": False,
    },

    # --- 14. Question transform ------------------------------------------
    "question_transform": {
        "label_en": "Turn it into a question",
        "label_ar": "حوّل إلى سؤال",
        "skill": ["grammar"],
        "requires_metadata": True,
        "required_metadata_keys": ["statement", "target_qword"],
        "supports_auto_grading": True,
        "supports_challenge": True,
        "renderer": "question_transform.html",
        "grader": "question_transform",
        "placeholder": False,
    },

    # --- 15. Mistake correction ------------------------------------------
    "mistake_correction": {
        "label_en": "Fix the sentence",
        "label_ar": "صحّح الجملة",
        "skill": ["grammar"],
        "requires_metadata": True,
        "required_metadata_keys": ["wrong_sentence", "corrected_sentence"],
        "supports_auto_grading": True,
        "supports_challenge": True,
        "renderer": "mistake_correction.html",
        "grader": "mistake_correction",
        "placeholder": False,
    },

    # --- 16. Translate to English ----------------------------------------
    "translate_to_english": {
        "label_en": "Translate to English",
        "label_ar": "ترجم إلى الإنجليزية",
        "skill": ["writing", "vocabulary"],
        "requires_metadata": True,
        "required_metadata_keys": ["source_ar", "accepted_answers"],
        "supports_auto_grading": True,
        "supports_challenge": True,
        "renderer": "translate_to_english.html",
        "grader": "accepted_answers",
        "placeholder": False,
    },

    # --- 17. Translate to Arabic -----------------------------------------
    "translate_to_arabic": {
        "label_en": "Pick the Arabic meaning",
        "label_ar": "اختر المعنى بالعربية",
        "skill": ["reading", "vocabulary"],
        "requires_metadata": True,
        "required_metadata_keys": ["source_en", "options", "correct_option_id"],
        "supports_auto_grading": True,
        "supports_challenge": True,
        "renderer": "translate_to_arabic.html",
        "grader": "tap_choice",
        "placeholder": False,
    },

    # --- 18. Speak this sentence (placeholder) ---------------------------
    "speak_this_sentence": {
        "label_en": "Read it out loud",
        "label_ar": "اقرأها بصوت",
        "skill": ["speaking"],
        "requires_metadata": True,
        "required_metadata_keys": ["sentence"],
        "supports_auto_grading": False,
        "supports_challenge": True,
        "renderer": "speaking_placeholder.html",
        "grader": "self_check",
        "placeholder": True,
    },

    # --- 19. Pronunciation check (placeholder) ---------------------------
    "pronunciation_check": {
        "label_en": "Practice the sound",
        "label_ar": "تدرّب على الصوت",
        "skill": ["speaking"],
        "requires_metadata": True,
        "required_metadata_keys": ["target_word"],
        "supports_auto_grading": False,
        "supports_challenge": True,
        "renderer": "speaking_placeholder.html",
        "grader": "self_check",
        "placeholder": True,
    },

    # --- 20. AI roleplay prompt — Phase 9.5: real in-card UI ---------------
    "ai_roleplay_prompt": {
        "label_en": "Roleplay with the tutor",
        "label_ar": "تمثيل مع المعلم الذكي",
        "skill": ["speaking"],
        "requires_metadata": True,
        "required_metadata_keys": ["scenario"],
        "supports_auto_grading": False,
        "supports_challenge": True,
        # Renderer wires the live Phase-7 endpoints when AI is on, and shows
        # a clear self-practice fallback when off. Either way it's NOT a
        # "coming soon" pill — the student can interact with the card.
        "renderer": "ai_roleplay_card.html",
        "grader": "self_check",
        "placeholder": True,
    },
}


# ---------------------------------------------------------------------------
# Legacy types — they aren't in the 20-name catalogue above but they're
# still valid (Classic Quiz uses them). The registry knows about them so
# they grade and render correctly in Challenge too.
# ---------------------------------------------------------------------------
LEGACY_TYPE_REGISTRY: dict[str, TypeSpec] = {
    "multiple_choice": {
        "label_en": "Pick one",
        "label_ar": "اختر إجابة",
        "skill": ["vocabulary", "grammar"],
        "requires_metadata": False,
        "required_metadata_keys": [],
        "supports_auto_grading": True,
        "supports_challenge": True,
        "renderer": "legacy_multiple_choice.html",
        "grader": "normalize_equality",
        "placeholder": False,
    },
    "fill_blank": {
        "label_en": "Fill the gap",
        "label_ar": "املأ الفراغ",
        "skill": ["grammar"],
        "requires_metadata": False,
        "required_metadata_keys": [],
        "supports_auto_grading": True,
        "supports_challenge": True,
        "renderer": "legacy_fill_blank.html",
        "grader": "normalize_equality",
        "placeholder": False,
    },
    "correction": {
        "label_en": "Fix the sentence",
        "label_ar": "صحّح الجملة",
        "skill": ["grammar"],
        "requires_metadata": False,
        "required_metadata_keys": [],
        "supports_auto_grading": True,
        "supports_challenge": True,
        "renderer": "legacy_text_input.html",
        "grader": "normalize_equality",
        "placeholder": False,
    },
    "sentence_ordering": {
        "label_en": "Put in order",
        "label_ar": "رتّب الكلمات",
        "skill": ["grammar"],
        "requires_metadata": False,
        "required_metadata_keys": [],
        "supports_auto_grading": True,
        "supports_challenge": True,
        "renderer": "legacy_text_input.html",
        "grader": "normalize_equality",
        "placeholder": False,
    },
    "translation": {
        "label_en": "Translate",
        "label_ar": "ترجم",
        "skill": ["writing"],
        "requires_metadata": False,
        "required_metadata_keys": [],
        "supports_auto_grading": True,
        "supports_challenge": True,
        "renderer": "legacy_text_input.html",
        "grader": "normalize_equality",
        "placeholder": False,
    },
    "short_answer": {
        "label_en": "Short answer",
        "label_ar": "إجابة قصيرة",
        "skill": ["writing"],
        "requires_metadata": False,
        "required_metadata_keys": [],
        "supports_auto_grading": True,
        "supports_challenge": True,
        "renderer": "legacy_text_input.html",
        "grader": "normalize_equality",
        "placeholder": False,
    },
    "speaking_prompt": {
        "label_en": "Speaking task",
        "label_ar": "تمرين محادثة",
        "skill": ["speaking"],
        "requires_metadata": False,
        "required_metadata_keys": [],
        "supports_auto_grading": False,
        "supports_challenge": True,
        "renderer": "speaking_placeholder.html",
        "grader": "self_check",
        "placeholder": True,
    },
    "writing_prompt": {
        "label_en": "Writing task",
        "label_ar": "تمرين كتابة",
        "skill": ["writing"],
        "requires_metadata": False,
        "required_metadata_keys": [],
        "supports_auto_grading": False,
        "supports_challenge": False,   # Classic Quiz only — too open-ended
        "renderer": "writing_placeholder.html",
        "grader": "self_check",
        "placeholder": True,
    },
    # Quiz Engine v2 types from the earlier prompt — re-export here so
    # the registry is the single source of truth.
    "listening_match": {
        "label_en": "Listening match",
        "label_ar": "مطابقة استماع",
        "skill": ["listening"],
        "requires_metadata": True,
        "required_metadata_keys": ["pairs"],
        "supports_auto_grading": True,
        "supports_challenge": False,   # too multi-step for a single card
        "renderer": "unsupported_question.html",
        "grader": "self_check",
        "placeholder": True,
    },
    "speaking_sentence_builder": {
        "label_en": "Speak from the table",
        "label_ar": "تكلّم من الجدول",
        "skill": ["speaking"],
        "requires_metadata": True,
        "required_metadata_keys": ["student_prompt"],
        "supports_auto_grading": False,
        "supports_challenge": True,
        "renderer": "speaking_placeholder.html",
        "grader": "self_check",
        "placeholder": True,
    },
}

ALL_TYPES: dict[str, TypeSpec] = {**LEGACY_TYPE_REGISTRY, **QUESTION_TYPE_REGISTRY}


# ---------------------------------------------------------------------------
# Public lookups
# ---------------------------------------------------------------------------

def get_spec(question_type: str) -> TypeSpec | None:
    """Return the registry entry for `question_type`, or None if unknown."""
    return ALL_TYPES.get(question_type)


def is_known(question_type: str) -> bool:
    return question_type in ALL_TYPES


def supports_challenge(question_type: str) -> bool:
    spec = ALL_TYPES.get(question_type)
    return bool(spec and spec.get("supports_challenge"))


def is_placeholder(question_type: str) -> bool:
    spec = ALL_TYPES.get(question_type)
    return bool(spec and spec.get("placeholder"))


def grader_key(question_type: str) -> str:
    spec = ALL_TYPES.get(question_type)
    return (spec or {}).get("grader", "")


def renderer_for(question_type: str) -> str:
    """Template filename — falls back to the 'unsupported' partial."""
    spec = ALL_TYPES.get(question_type)
    return (spec or {}).get("renderer", "unsupported_question.html")


def label(question_type: str, *, lang: str = "en") -> str:
    spec = ALL_TYPES.get(question_type, {})
    if lang.startswith("ar"):
        return spec.get("label_ar") or spec.get("label_en") or question_type
    return spec.get("label_en") or question_type


def validate_metadata(question_type: str, metadata: dict) -> list[str]:
    """Return a list of missing required keys for this type (empty list = ok)."""
    spec = ALL_TYPES.get(question_type)
    if spec is None or not spec.get("requires_metadata"):
        return []
    required = spec.get("required_metadata_keys") or []
    return [k for k in required if k not in (metadata or {})]
