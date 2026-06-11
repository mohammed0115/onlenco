"""Builder for the listen_build_sentence Daily Quiz item (Prompt 18.3B).

A listen_build item is NOT a new DB item_type — it reuses ``item_type="word_order"``
with ``metadata["listen_build"]=True``. The student hears a short sentence and
taps its (scrambled) words into the right order. Grading is the same as
word_order (server-side, token-order compare in ``daily_grading``).

Kept A1-simple. The presented option order is deliberately NOT the correct
order (so there is a real task) but is deterministic (no randomness needed —
the grader compares submitted tokens to ``correct_answer``).
"""
from __future__ import annotations

# Short, beginner-safe sentences. The correct order lives in correct_answer;
# options are shown alphabetically so the picker has to rebuild the sentence.
_SENTENCES = (
    "I am a student",
    "She is my friend",
    "We are happy today",
    "He has a red car",
    "They live in the city",
    "My name is Sara",
)


def build_listen_build_item(cefr_level: str = "A1", language: str = "en", *, seed: int = 0) -> dict:
    """Return a ``composed``-shaped dict for one listen_build item."""
    sentence = _SENTENCES[seed % len(_SENTENCES)]
    words = sentence.split()
    options = sorted(words, key=str.lower)   # deterministic, not the answer order
    band = (cefr_level or "A1")[:2].upper()
    lvl = "A1" if band in ("A0", "A1") else cefr_level
    ar = language == "ar"
    return {
        "item_type": "word_order",
        "title": "استمع وكوّن الجملة" if ar else "Listen and build",
        "instructions": (
            "استمع للجملة ثم اضغط الكلمات بالترتيب الصحيح."
            if ar else "Listen, then tap the words in the correct order."
        ),
        "content_text": "",
        "question": "استمع وكوّن الجملة." if ar else "Listen and build the sentence.",
        "options": options,
        "correct_answer": sentence,
        "cefr_level": lvl,
        "skill": "listening",
        "difficulty_score": 0.2,
        "estimated_minutes": 2,
        "metadata": {"listen_build": True, "source": "listen_build"},
    }
