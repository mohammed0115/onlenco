"""End-of-call evaluation for the voice tutor.

Reads the persisted user-side TutorMessage rows for a conversation,
derives a CEFR level + sub-scores, and writes one VoiceCallEvaluation
row per conversation. Idempotent: re-running on the same conversation
overwrites the prior eval (one OneToOne row).

The scorer is intentionally heuristic for now — word count + unique
token ratio + turn count → CEFR + 0-100 sub-scores. This avoids a
dependency on the AI assessor inside the voice-call hot path and means
the eval row is always written even when the LLM service is down. An
AI-driven assessor can be slotted in later by swapping out `_score`.
"""
from __future__ import annotations

import logging
import re
from typing import Iterable

from ..models import TutorConversation, TutorMessage, VoiceCallEvaluation

logger = logging.getLogger(__name__)


_WORD_RE = re.compile(r"[A-Za-z']+")


def _english_tokens(text: str) -> list[str]:
    return [m.group(0).lower() for m in _WORD_RE.finditer(text)]


def _score(user_texts: Iterable[str], turns_count: int, seconds: int) -> dict:
    """Heuristic scorer. Returns dict matching the VoiceCallEvaluation fields.

    The mapping (rough, but defensible for placement bootstrapping):

      total English words → fluency_score
      unique/total ratio  → vocabulary_score
      avg words per turn  → grammar_score (proxy: longer turns = more clauses)
      turns + words combo → overall_score → CEFR
    """
    all_tokens: list[str] = []
    for t in user_texts:
        all_tokens.extend(_english_tokens(t))
    total = len(all_tokens)
    unique = len(set(all_tokens))
    avg_per_turn = (total / max(1, turns_count))

    # Fluency: scaled by total words, capped at ~150 words = 100.
    fluency = max(0, min(100, int((total / 150.0) * 100)))
    # Vocabulary: unique/total ratio AND raw uniques.
    diversity = unique / max(1, total)            # 0..1
    vocabulary = max(0, min(100, int(min(unique * 4, 100) * (0.4 + 0.6 * diversity))))
    # Grammar (proxy): avg words per turn — short = limited, long = complex.
    grammar = max(0, min(100, int((avg_per_turn / 12.0) * 100)))
    # Pronunciation can't be assessed from text alone — give a soft mid score
    # tied to fluency so the UI has something to show.
    pronunciation = max(20, min(100, int(40 + fluency * 0.5)))
    overall = int(round(0.35 * fluency + 0.30 * vocabulary + 0.25 * grammar + 0.10 * pronunciation))

    cefr = _overall_to_cefr(overall, unique)
    return {
        "fluency_score": fluency,
        "vocabulary_score": vocabulary,
        "grammar_score": grammar,
        "pronunciation_score": pronunciation,
        "overall_score": overall,
        "cefr_level": cefr,
        "word_count": total,
        "turns_count": turns_count,
        "seconds": int(seconds),
        "summary": (
            f"{total} words across {turns_count} turns "
            f"({unique} unique). Estimated level: {cefr}."
        ),
    }


def _overall_to_cefr(overall: int, unique_words: int) -> str:
    # Combined gate: need both score and vocabulary breadth to climb levels.
    # Prevents a long single-word "yes yes yes" from scoring well.
    if overall < 15 or unique_words < 8:
        return "A0"
    if overall < 30 or unique_words < 25:
        return "A1"
    if overall < 45 or unique_words < 50:
        return "A2"
    if overall < 60 or unique_words < 80:
        return "B1"
    if overall < 75:
        return "B2"
    if overall < 90:
        return "C1"
    return "C2"


def evaluate_voice_call(
    conversation: TutorConversation,
    seconds: int = 0,
) -> VoiceCallEvaluation | None:
    """Score the conversation and persist a VoiceCallEvaluation.

    Best-effort: never raises. Returns None when there's no usable
    user transcript to score (so the caller can decide whether to
    nudge the user to try again).
    """
    if conversation is None:
        return None
    msgs = list(
        TutorMessage.objects
        .filter(conversation=conversation, role="user")
        .order_by("created_at")
        .values_list("content", flat=True)
    )
    if not msgs:
        return None
    try:
        scored = _score(msgs, turns_count=len(msgs), seconds=seconds)
    except Exception:
        logger.exception("evaluate_voice_call: scoring failed for conv=%s", conversation.pk)
        return None
    eval_obj, _ = VoiceCallEvaluation.objects.update_or_create(
        conversation=conversation,
        defaults=scored,
    )
    return eval_obj
