"""Builder for the `tutor_reply` task.

Input  : student question + learning profile context
Output : teacher-like response

Source: `tutor.TutorMessage` pairs — a `user` message followed by the
next `assistant` message in the same conversation. The user's profile
(level, weakness summary) is denormalised into the input so the model
sees the same context the live tutor saw."""
from __future__ import annotations

import logging
from typing import Iterable

from learning_core.models import StudentLearningProfile, UserWeakness
from tutor.models import TutorConversation, TutorMessage

from . import _base
from ..models import DatasetBuild
from .. import constants as C

logger = logging.getLogger(__name__)


def _user_context(user_id: int) -> dict:
    profile = StudentLearningProfile.objects.filter(user_id=user_id).first()
    weaknesses = (
        UserWeakness.objects
        .filter(user_id=user_id)
        .select_related("skill", "grammar_topic")
        .order_by("-priority_score")[:3]
    )
    return {
        "cefr_level": profile.current_cefr_level if profile else "",
        "weaknesses": [
            {
                "skill": w.skill.category if w.skill_id and w.skill else "",
                "topic": w.grammar_topic.name if w.grammar_topic_id and w.grammar_topic else "",
            }
            for w in weaknesses
        ],
    }


def _iter_tutor_pairs(filters: dict) -> Iterable[dict]:
    convs = TutorConversation.objects.all()
    if filters.get("user_id"):
        convs = convs.filter(user_id=int(filters["user_id"]))
    for conv in convs.iterator(chunk_size=200):
        msgs = list(
            TutorMessage.objects
            .filter(conversation=conv)
            .order_by("created_at")
        )
        # Slide: take every (user, assistant) pair where assistant is the
        # immediate response to that user message.
        i = 0
        while i < len(msgs) - 1:
            if msgs[i].role == "user" and msgs[i + 1].role == "assistant":
                user_msg = msgs[i]
                asst_msg = msgs[i + 1]
                if user_msg.content.strip() and asst_msg.content.strip():
                    ctx = _user_context(conv.user_id) if hasattr(conv, "user_id") else {}
                    yield {
                        "task_type": C.TASK_TUTOR_REPLY,
                        "source_type": "TutorMessage",
                        "source_id": asst_msg.id,
                        "cefr_level": ctx.get("cefr_level") or "",
                        "skill": "",
                        "quality_score": 75,
                        "language": "en",
                        "input": {
                            "student_question": user_msg.content,
                            "context": ctx,
                        },
                        "output": {
                            "tutor_reply": asst_msg.content,
                        },
                    }
                i += 2
            else:
                i += 1


def build(build_row: DatasetBuild, *, min_quality: int = 0) -> dict:
    return _base.persist_stream(
        build_row, _iter_tutor_pairs(build_row.filters or {}),
        min_quality=min_quality, require_cefr=False,
    )
