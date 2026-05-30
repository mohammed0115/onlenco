"""Build a unit dict for any non-A0 level from a topic descriptor.

The output matches the exact shape of entries in
`onlenco_beginner_seed_data.UNITS`, so the existing
`build_content_html`, `build_content_ar`, `build_image_prompts`, and
`build_audio_scripts` work without modification.

Inputs:
  - level dict from `onlenco_level_descriptors.LEVELS`
  - topic_idx — index into level['topics'] (0..47)

Output: a UNIT-shaped dict consumable by the generalized seed command.
"""
from __future__ import annotations


# Recurring Onlenco students — same cast as the A0 pack (Method Spec §11).
CAST = ["Amani", "Yusuf", "Noor", "Kareem", "Salma", "Omar",
        "Layla", "Tarek", "Hala", "Rashid"]


def _example_pair(en_template: str, ar_hint: str, n: int = 4) -> list[tuple[str, str]]:
    """Produce N (en, ar) example pairs from a base template.

    The English template is rotated by swapping in different cast names so
    students see the same construction across characters. The Arabic
    translation is a literal paraphrase generated from the EN pattern when
    `ar_hint` is empty.
    """
    if not en_template or en_template == "—":
        return [("Practice with the new construction.",
                 "تدرب على التركيب الجديد.")]
    base_en = en_template
    base_ar = ar_hint or f"المعنى: {en_template}"
    swaps = [
        (en_template, base_ar),
        (en_template.replace("I ", f"{CAST[0]} ").replace("My ", f"{CAST[0]}'s "),
         base_ar.replace("أنا ", f"{CAST[0]} ")),
        (en_template.replace("She ", f"{CAST[2]} ").replace("she ", f"{CAST[2]} "),
         base_ar.replace("هي ", f"{CAST[2]} ")),
        (en_template.replace("He ", f"{CAST[5]} ").replace("he ", f"{CAST[5]} "),
         base_ar.replace("هو ", f"{CAST[5]} ")),
    ]
    out = []
    for en, ar in swaps[:n]:
        out.append((en, ar))
    return out


def _dialogue_from_example(example_en: str, characters: tuple[str, str]) -> list[tuple[str, str]]:
    """Produce a 4-line mini dialogue around the example sentence."""
    a, b = characters
    if not example_en or example_en == "—":
        return [
            (a, "Let's talk about today's topic."),
            (b, "Sure — what should we cover?"),
            (a, "Let's practice together."),
            (b, "Great. I'll start."),
        ]
    return [
        (a, f"Can you give me an example?"),
        (b, f"Sure. {example_en}"),
        (a, "Got it. Let me try one."),
        (b, "Go ahead — I'm listening."),
    ]


def _checklist_from_topic(topic_title_en: str, topic_title_ar: str,
                           new_lang_en: str, new_lang_ar: str
                           ) -> list[tuple[str, str]]:
    """Two-item checklist derived from the topic title + new language."""
    return [
        (
            f"I can use {topic_title_en.lower()}.",
            f"أستطيع استخدام {topic_title_ar}.",
        ),
        (
            f"I understand the pattern: {new_lang_en or '(see content)'}.",
            f"أفهم النمط: {new_lang_ar or '(انظر المحتوى)'}.",
        ),
    ]


def _topic_cluster_to_review_group(cluster_idx: int) -> str:
    """The 6 clusters map directly to R1..R6 — same convention as A0."""
    return f"R{int(cluster_idx)}"


def _image_idea_for_topic(title_en: str, lesson_type: str) -> str:
    """Generic but original image idea using Onlenco cast & brand rules."""
    cast_name = CAST[hash(title_en) % len(CAST)]
    other = CAST[(hash(title_en) + 3) % len(CAST)]
    if lesson_type == "vocabulary":
        return (
            f"Flat illustration tile grid for '{title_en}' — Onlenco "
            f"palette, soft pastel background, 2 px outlines, no text, "
            f"no DK trade dress."
        )
    if lesson_type == "speaking":
        return (
            f"{cast_name} and {other} in conversation about '{title_en}', "
            f"speech bubbles visible, flat Onlenco illustration, soft "
            f"green background, no text inside speech bubbles."
        )
    if lesson_type == "writing":
        return (
            f"{cast_name} writing thoughtfully at a desk, papers and "
            f"notebook visible, flat Onlenco illustration, soft cream "
            f"background, no readable text."
        )
    if lesson_type == "reading":
        return (
            f"{cast_name} reading a tablet or book intently, flat "
            f"Onlenco illustration, soft blue background, no readable "
            f"text on screen."
        )
    # default — grammar / mixed
    return (
        f"Abstract Onlenco-style visual hint for '{title_en}'. Soft "
        f"pastel background, geometric shapes, no text, no DK trade "
        f"dress, no realistic photographs."
    )


def build_unit_dict(level: dict, topic_idx: int) -> dict:
    """Assemble a full unit dict from a level + topic descriptor."""
    topic = level["topics"][topic_idx]
    (title_en, title_ar, cluster_idx,
     new_lang_en, new_lang_ar,
     example_en, lesson_type, minutes) = topic

    examples = _example_pair(example_en, new_lang_ar, n=4)
    pair_chars = (CAST[topic_idx % len(CAST)],
                  CAST[(topic_idx + 3) % len(CAST)])
    dialogue = _dialogue_from_example(example_en, pair_chars)
    checklist = _checklist_from_topic(title_en, title_ar, new_lang_en, new_lang_ar)

    return {
        "n": topic_idx + 1,
        "review_group": _topic_cluster_to_review_group(cluster_idx),
        "title_en": title_en,
        "title_ar": title_ar,
        "cefr": level["code"],
        "minutes": minutes,
        "lesson_type": lesson_type,
        "new_language_en": new_lang_en or "(see content_html)",
        "new_language_ar": new_lang_ar or "(انظر محتوى الدرس)",
        "vocabulary_en": (
            f"Topic vocabulary: {title_en}. See the lesson examples for "
            f"the in-context word list."
        ),
        "vocabulary_ar": (
            f"مفردات الموضوع: {title_ar}. راجع أمثلة الدرس للكلمات في سياقها."
        ),
        "skill_en": (
            f"Confidently use {title_en.lower()} at {level['code']} level."
        ),
        "skill_ar": (
            f"استخدم {title_ar} بثقة على مستوى {level['code']}."
        ),
        "grammar_en": new_lang_en or "—",
        "grammar_ar": new_lang_ar or "—",
        "pronunciation_en": "",  # filled per-topic only when distinctive
        "pronunciation_ar": "",
        "image_idea": _image_idea_for_topic(title_en, lesson_type),
        "speaking_goal_en": (
            f"Record yourself producing 3 original sentences using "
            f"'{title_en.lower()}'."
        ),
        "speaking_goal_ar": (
            f"سجّل نفسك تنتج 3 جمل أصلية تستخدم '{title_ar}'."
        ),
        "listening_goal_en": (
            f"Listen to the model audio and identify the {level['code']}-level "
            f"construction in use."
        ),
        "listening_goal_ar": (
            f"استمع للنموذج الصوتي وحدّد التركيب من مستوى {level['code']}."
        ),
        "quiz_goal_en": (
            f"8 mixed items testing recognition, production, and meaning "
            f"of '{title_en.lower()}'."
        ),
        "ai_tutor_goal_en": (
            f"Two-minute drill — tutor and student exchange 4 prompts "
            f"using the new construction. One correction at a time."
        ),
        "ai_tutor_goal_ar": (
            f"تدريب لدقيقتين — المعلم والطالب يتبادلان 4 محفّزات تستخدم "
            f"التركيب الجديد. تصحيح واحد في كل مرة."
        ),
        "examples": examples,
        "dialogue": dialogue,
        "checklist": checklist,
        "arabic_tip": (
            f"في مستوى {level['code']}، الهدف هو الطلاقة وليس الكمال — "
            f"حاول استخدام التركيب الجديد في حياتك اليومية مرة واحدة "
            f"على الأقل اليوم."
        ),
        "common_mistake_ar": (
            f"خطأ شائع للناطقين بالعربية: نقل البنية حرفياً من العربية "
            f"إلى الإنجليزية. حاول التفكير بالإنجليزية مباشرة."
        ),
    }


def build_all_units_for_level(level: dict) -> list[dict]:
    """Produce the full 48-unit list for one level."""
    return [build_unit_dict(level, i) for i in range(len(level["topics"]))]
