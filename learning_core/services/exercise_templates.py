"""Local fallback exercise templates.

Used when the AI generator fails or is not configured. Each template is
indexed by skill category + grammar topic name (case-insensitive). Topics
without a template fall through to a generic multiple-choice prompt.
"""
from __future__ import annotations

from typing import Iterable

from learning_core.models import AdaptiveExercise, GrammarTopic, Skill


GENERIC_TEMPLATES = [
    {
        "question_type": "multiple_choice",
        "question": "Choose the correct option: She ___ to school every day.",
        "options": ["go", "goes", "going", "went"],
        "correct_answer": "goes",
        "explanation": "Third-person singular present takes -es.",
        "cefr_level": "A1",
        "difficulty_score": 0.2,
    },
    {
        "question_type": "fill_blank",
        "question": "Yesterday I ___ (eat) breakfast at 7am.",
        "options": [],
        "correct_answer": "ate",
        "explanation": "Past simple of 'eat' is 'ate'.",
        "cefr_level": "A2",
        "difficulty_score": 0.4,
    },
    {
        "question_type": "correction",
        "question": "Correct the sentence: He don't like coffee.",
        "options": [],
        "correct_answer": "He doesn't like coffee.",
        "explanation": "Third-person singular uses 'doesn't'.",
        "cefr_level": "A2",
        "difficulty_score": 0.35,
    },
    {
        "question_type": "multiple_choice",
        "question": "Choose: I ___ in this city since 2018.",
        "options": ["live", "have lived", "lived", "am living"],
        "correct_answer": "have lived",
        "explanation": "Present perfect for actions starting in the past and continuing now.",
        "cefr_level": "B1",
        "difficulty_score": 0.55,
    },
]


TOPIC_TEMPLATES = {
    "subject-verb agreement": [
        {
            "question_type": "correction",
            "question": "Correct: He go to the gym on Mondays.",
            "options": [],
            "correct_answer": "He goes to the gym on Mondays.",
            "explanation": "Third-person singular 'he' takes 'goes'.",
            "cefr_level": "A1",
            "difficulty_score": 0.25,
        },
    ],
    "articles": [
        {
            "question_type": "fill_blank",
            "question": "Fill in: I saw ___ elephant at ___ zoo.",
            "options": [],
            "correct_answer": "an, the",
            "explanation": "'an' before vowel sound; 'the' for a specific zoo.",
            "cefr_level": "A1",
            "difficulty_score": 0.2,
        },
    ],
    "past simple": [
        {
            "question_type": "fill_blank",
            "question": "Last week she ___ (visit) her grandmother.",
            "options": [],
            "correct_answer": "visited",
            "explanation": "Regular verb past tense adds -ed.",
            "cefr_level": "A2",
            "difficulty_score": 0.35,
        },
    ],
    "present perfect": [
        {
            "question_type": "multiple_choice",
            "question": "She ___ Paris three times.",
            "options": ["visit", "visited", "has visited", "is visiting"],
            "correct_answer": "has visited",
            "explanation": "Present perfect for life experiences with a count.",
            "cefr_level": "B1",
            "difficulty_score": 0.5,
        },
    ],
}


def render_fallback(
    *,
    skill: Skill | None,
    topic: GrammarTopic | None,
    cefr_level: str,
    difficulty: float,
    count: int,
) -> list[dict]:
    """Return a list of dicts shaped like the AI output. Never raises."""
    pool: list[dict] = []
    if topic and topic.name:
        pool.extend(TOPIC_TEMPLATES.get(topic.name.lower(), []))
    pool.extend(GENERIC_TEMPLATES)

    out: list[dict] = []
    seen_questions: set[str] = set()
    for template in pool:
        if template["question"] in seen_questions:
            continue
        seen_questions.add(template["question"])
        out.append(
            {
                **template,
                "skill": skill.category if skill else "",
                "skill_id": skill.id if skill else None,
                "topic_id": topic.id if topic else None,
                "grammar_topic": topic.name if topic else "",
                "cefr_level": cefr_level or template.get("cefr_level", ""),
                "difficulty_score": float(
                    difficulty if difficulty is not None else template.get("difficulty_score", 0.5)
                ),
            }
        )
        if len(out) >= count:
            break
    return out
