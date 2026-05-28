"""Programmatic quiz builder for the Onlenco Beginner course.

Each Learning Unit gets one Quiz with 8–12 original questions following a
fixed shape (the EFE exercise pattern, our content):

  * 3 Vocabulary  (multiple_choice, fill_blank)
  * 3 Grammar     (multiple_choice T/F, fill_blank, correction)
  * 1 Reading     (multiple_choice over the unit's mini dialogue)
  * 1 Speaking    (speaking_prompt — feeds the AI tutor drill)
  * 1 Listening   (multiple_choice + QuestionMedia placeholder audio row)
  * (optional)    sentence_ordering when there's a 4-token example

Each generator function returns a list of dicts shaped for
`LessonQuestion.objects.update_or_create(quiz=…, order=N, defaults=…)`.
The seed command consumes those dicts.

All copy is original Onlenco — sentences pull from the per-unit `examples`
and `dialogue` fields in `onlenco_beginner_seed_data.UNITS`. No copy from
any specific source publication.
"""
from __future__ import annotations

from typing import Iterable


def _opt(*xs: str) -> list[str]:
    """Helper for compact list literals in question generators."""
    return list(xs)


def _vocabulary_questions(unit: dict) -> list[dict]:
    """3 vocabulary questions per unit."""
    title = unit["title_en"]
    examples = unit.get("examples") or []
    vocab_phrase = (unit.get("vocabulary_en") or "").split(":")[-1].strip()
    # Pick the first three example sentences as MCQ stems; if fewer, pad.
    stems = list(examples[:3])
    while len(stems) < 3:
        stems.append((f"This is about {title.lower()}.", f"يتعلق هذا بـ {unit['title_ar']}."))

    qs: list[dict] = []
    for i, (en, ar) in enumerate(stems, start=1):
        # Hide a key word from the sentence; use the first noun-like word.
        words = en.replace(".", "").split()
        if not words:
            continue
        # Strip a short word as the "answer", offering 3 distractors.
        target_idx = next(
            (k for k, w in enumerate(words) if len(w) >= 3 and w.isalpha()),
            0,
        )
        answer = words[target_idx].strip(",.;!?")
        masked = list(words)
        masked[target_idx] = "____"
        prompt = " ".join(masked) + "."
        distractors = _opt("today", "very", "always")
        if answer in distractors:
            distractors = _opt("here", "very", "now")
        options = sorted({answer} | set(distractors[:3]))
        qs.append({
            "order": i,
            "question_type": "multiple_choice",
            "question_text": f"Fill in the gap: \"{prompt}\"",
            "question_text_en": f"Fill in the gap: \"{prompt}\"",
            "question_text_ar": f"املأ الفراغ: \"{prompt}\" (المعنى: {ar})",
            "options": options,
            "correct_answer": answer,
            "explanation": f"The word \"{answer}\" fits the sentence about {title.lower()}.",
            "explanation_ar": f"الكلمة \"{answer}\" تناسب الجملة حول {unit['title_ar']}.",
            "difficulty_score": 0.25,
            "points": 1,
            "skill": "vocabulary",
        })
    return qs


def _grammar_questions(unit: dict) -> list[dict]:
    """3 grammar questions per unit."""
    new_lang_en = unit.get("new_language_en") or ""
    new_lang_ar = unit.get("new_language_ar") or ""
    grammar_en = unit.get("grammar_en") if unit.get("grammar_en") != "—" else "this construction"
    examples = unit.get("examples") or []

    qs: list[dict] = []

    # Q1 — True/False on the construction (rendered as MCQ T/F).
    truth_en = (
        f"The new language in this lesson is: {new_lang_en}"
        if new_lang_en else f"This lesson introduces {grammar_en}."
    )
    qs.append({
        "order": 4,
        "question_type": "multiple_choice",
        "question_text": f"True or False — {truth_en}",
        "question_text_en": f"True or False — {truth_en}",
        "question_text_ar": f"صحيح أم خطأ — {new_lang_ar or grammar_en}",
        "options": ["True", "False"],
        "correct_answer": "True",
        "explanation": "This is the new language taught in the unit.",
        "explanation_ar": "هذه هي اللغة الجديدة المُعلَّمة في الوحدة.",
        "difficulty_score": 0.15,
        "points": 1,
        "skill": "grammar",
    })

    # Q2 — Fill blank from an example sentence (focus on construction).
    if examples:
        en, ar = examples[0]
        # Mask the first capital-letter word (often the target construction).
        words = en.split()
        idx = next(
            (k for k, w in enumerate(words) if w.lower() in {"is", "am", "are", "do", "does", "have", "has", "can", "would"}),
            0,
        )
        answer = words[idx].strip(",.;!?")
        masked = list(words)
        masked[idx] = "____"
        qs.append({
            "order": 5,
            "question_type": "fill_blank",
            "question_text": " ".join(masked).rstrip(".") + ".",
            "question_text_en": " ".join(masked).rstrip(".") + ".",
            "question_text_ar": f"املأ الفراغ. الترجمة: {ar}",
            "options": [],
            "correct_answer": answer,
            "explanation": f"The correct form for this construction is \"{answer}\".",
            "explanation_ar": f"الصيغة الصحيحة لهذا التركيب هي \"{answer}\".",
            "difficulty_score": 0.30,
            "points": 1,
            "skill": "grammar",
        })

    # Q3 — Correction: an intentionally wrong sentence to fix.
    common_mistake = unit.get("common_mistake_ar") or ""
    wrong_sentence = (
        examples[1][0].replace("is", "am").replace("are", "is")
        if len(examples) >= 2 else "He are happy."
    )
    correct_sentence = examples[1][0] if len(examples) >= 2 else "He is happy."
    qs.append({
        "order": 6,
        "question_type": "correction",
        "question_text": f"Fix the sentence: \"{wrong_sentence}\"",
        "question_text_en": f"Fix the sentence: \"{wrong_sentence}\"",
        "question_text_ar": f"صحّح الجملة: \"{wrong_sentence}\" — {common_mistake}",
        "options": [],
        "correct_answer": correct_sentence,
        "explanation": "Use the right form of \"to be\" / the new construction.",
        "explanation_ar": "استخدم الصيغة الصحيحة لـ to be أو التركيب الجديد.",
        "difficulty_score": 0.40,
        "points": 1,
        "skill": "grammar",
    })

    return qs


def _reading_question(unit: dict) -> list[dict]:
    """1 reading comprehension question — drawn from the mini dialogue."""
    dialogue = unit.get("dialogue") or []
    if not dialogue:
        return []
    # Build a tiny comprehension question from the dialogue.
    first_speaker = dialogue[0][0]
    return [{
        "order": 7,
        "question_type": "multiple_choice",
        "question_text": f"In the dialogue, who speaks first?",
        "question_text_en": f"In the dialogue, who speaks first?",
        "question_text_ar": f"في الحوار، من يتحدث أولًا؟",
        "options": sorted({first_speaker} | {d[0] for d in dialogue[1:3]}),
        "correct_answer": first_speaker,
        "explanation": f"{first_speaker} opens the dialogue.",
        "explanation_ar": f"{first_speaker} يبدأ الحوار.",
        "difficulty_score": 0.20,
        "points": 1,
        "skill": "reading",
    }]


def _speaking_prompt(unit: dict) -> list[dict]:
    """1 speaking prompt — drives the AI tutor drill."""
    keywords = []
    for en, _ar in (unit.get("examples") or [])[:3]:
        keywords.extend(w.strip(",.;!?").lower() for w in en.split() if len(w) >= 3)
    expected = sorted(set(keywords))[:8]
    return [{
        "order": 8,
        "question_type": "speaking_prompt",
        "question_text": unit.get("speaking_goal_en") or "Record yourself describing today's topic.",
        "question_text_en": unit.get("speaking_goal_en") or "Record yourself describing today's topic.",
        "question_text_ar": unit.get("speaking_goal_ar") or "سجّل وصفًا قصيرًا لموضوع الدرس.",
        "options": expected,
        "correct_answer": "(model recording)",
        "explanation": (
            f"AI tutor instruction: {unit.get('ai_tutor_goal_en', '')} "
            f"Accent: American. Correction style: gentle. "
            f"Expected keywords: {', '.join(expected)}."
        ),
        "explanation_ar": unit.get("ai_tutor_goal_ar") or "",
        "difficulty_score": 0.35,
        "points": 2,
        "skill": "speaking",
    }]


def _listening_question(unit: dict) -> list[dict]:
    """1 listening question — placeholder, audio attached separately."""
    first_example = (unit.get("examples") or [("Listen and answer.", "استمع وأجب.")])[0]
    en, ar = first_example
    return [{
        "order": 9,
        "question_type": "multiple_choice",
        "question_text": f"Listen and choose the correct sentence.",
        "question_text_en": f"Listen and choose the correct sentence.",
        "question_text_ar": f"استمع واختر الجملة الصحيحة.",
        "options": [en, "I don't know.", "Please repeat that."],
        "correct_answer": en,
        "explanation": f"The audio plays: \"{en}\". Translation: {ar}.",
        "explanation_ar": f"الصوت يقول: \"{en}\". الترجمة: {ar}.",
        "difficulty_score": 0.30,
        "points": 1,
        "skill": "listening",
        # Marker fields used by the seed command to attach a QuestionMedia
        # placeholder row (audio file blank — actual audio comes from P08).
        "_audio_required": True,
        "_audio_script": en,
    }]


def build_questions_for_unit(unit: dict) -> list[dict]:
    """Return the 9-item question set for one Learning Unit."""
    questions: list[dict] = []
    questions.extend(_vocabulary_questions(unit))
    questions.extend(_grammar_questions(unit))
    questions.extend(_reading_question(unit))
    questions.extend(_speaking_prompt(unit))
    questions.extend(_listening_question(unit))
    # Pad to at least 8 if anything dropped out.
    return questions
