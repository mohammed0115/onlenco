"""Chapter summarisation — AI when available, deterministic fallback otherwise.

Public API:
    summarize_chapter(chapter, language="en") -> dict
        {summary, key_points: list[str], source: "ai"|"heuristic"}

Saves the result to `Chapter.metadata["summary"]` so the dashboard /
mobile API can read it without re-calling the LLM.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Optional

import requests
from django.conf import settings

from library.models import Chapter

logger = logging.getLogger(__name__)

MAX_INPUT_CHARS = 8000


def _heuristic_summary(text: str, *, language: str) -> dict:
    """Cheap extractive summary: first 2 + last sentence + 5 long sentences.

    Good enough as a fallback so users see *something* useful rather than
    an empty card when the AI is unavailable.
    """
    s = (text or "").strip()
    if not s:
        return {"summary": "", "key_points": [], "source": "heuristic"}
    sentences = [
        x.strip()
        for x in re.split(r"(?<=[.!?])\s+|(?<=[؟!۔])\s+", s)
        if x.strip()
    ]
    if not sentences:
        return {"summary": s[:240], "key_points": [], "source": "heuristic"}
    head = sentences[:2]
    long_ones = sorted(sentences[2:], key=len, reverse=True)[:5]
    summary_parts = head + ([sentences[-1]] if len(sentences) > 2 else [])
    return {
        "summary": " ".join(summary_parts)[:480],
        "key_points": [x[:200] for x in long_ones],
        "source": "heuristic",
    }


def _build_prompt(chapter: Chapter, language: str) -> tuple[str, str]:
    sys = (
        "You are an English-learning content assistant. Produce a "
        "short summary (2-3 sentences) and 3-5 key points from the "
        "given chapter text. Reply in "
        f"{'Arabic' if language == 'ar' else 'English'}. "
        "Output strict JSON with keys: summary (string), "
        "key_points (array of strings)."
    )
    body = (chapter.body or "")[:MAX_INPUT_CHARS]
    user = f"Chapter title: {chapter.title}\n\nChapter text:\n{body}"
    return sys, user


def _call_ai(chapter: Chapter, language: str) -> Optional[dict]:
    if not settings.AI_API_KEY:
        return None
    sys, user = _build_prompt(chapter, language)
    try:
        # Centralised ai_usage wrapper (Prompt 12A) handles metering + logging.
        from ai_usage import constants as AC
        from ai_usage.services import ai_client

        resp_data = ai_client.chat(
            [
                {"role": "system", "content": sys},
                {"role": "user", "content": user},
            ],
            feature=AC.FEATURE_LIBRARY, model=settings.AI_MODEL,
            extra_payload={"max_tokens": 350, "temperature": 0.3,
                           "response_format": {"type": "json_object"}},
            timeout=45,
        )
        content = resp_data["choices"][0]["message"].get("content") or "{}"
        data = json.loads(content)
        summary = (data.get("summary") or "").strip()
        key_points = [
            str(p).strip()[:200]
            for p in (data.get("key_points") or [])
            if str(p).strip()
        ][:5]
        if not summary:
            return None
        return {
            "summary": summary[:600],
            "key_points": key_points,
            "source": "ai",
        }
    except Exception as e:
        logger.warning("summarizer: AI call failed: %s", e)
        return None


def summarize_chapter(chapter: Chapter, language: str = "en") -> dict:
    """Persist + return a chapter summary. Idempotent: re-uses cached
    metadata['summary'] when present unless `force=True`."""
    cached = (chapter.metadata or {}).get("summary") if hasattr(chapter, "metadata") else None
    if cached and isinstance(cached, dict) and cached.get("summary"):
        return cached

    result = _call_ai(chapter, language) or _heuristic_summary(chapter.body, language=language)
    # Persist if Chapter has a metadata field; otherwise just return.
    try:
        if hasattr(chapter, "metadata"):
            meta = chapter.metadata or {}
            meta["summary"] = result
            chapter.metadata = meta
            chapter.save(update_fields=["metadata"])
    except Exception:
        # No metadata column — that's fine, summary is still returned.
        pass
    return result
