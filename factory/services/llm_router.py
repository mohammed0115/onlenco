"""Local-first LLM router.

Resolution order:
  1. Local endpoint (settings.AI_LOCAL_API_BASE) — preferred for cost,
     privacy, and latency. Used when configured AND reachable.
  2. OpenAI-compatible fallback (settings.AI_API_KEY + AI_API_BASE).
  3. None — caller is expected to drop back to templates / heuristics.

The router is intentionally thin — it owns *transport* and *failover*,
not prompt engineering. Callers (quality validator, AI generator, etc.)
build their own messages.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_S = 30
LOCAL_BASE_SETTING = "AI_LOCAL_API_BASE"   # e.g. "http://localhost:8080/v1"
LOCAL_MODEL_SETTING = "AI_LOCAL_MODEL"     # e.g. "llama-3-8b-instruct"
LOCAL_KEY_SETTING = "AI_LOCAL_API_KEY"     # optional


def _local_endpoint() -> tuple[str, str, str] | None:
    base = getattr(settings, LOCAL_BASE_SETTING, "") or ""
    if not base:
        return None
    model = getattr(settings, LOCAL_MODEL_SETTING, "") or "local"
    key = getattr(settings, LOCAL_KEY_SETTING, "") or ""
    return base.rstrip("/"), model, key


def _openai_endpoint() -> tuple[str, str, str] | None:
    key = getattr(settings, "AI_API_KEY", "") or ""
    if not key:
        return None
    base = (getattr(settings, "AI_API_BASE", "") or "https://api.openai.com/v1").rstrip("/")
    model = getattr(settings, "AI_MODEL", "gpt-4o-mini")
    return base, model, key


def _post_chat(base: str, model: str, key: str, messages: list[dict],
               *, json_mode: bool, timeout: int) -> dict | None:
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    payload: dict = {
        "model": model,
        "messages": messages,
        "temperature": 0.4,
        "max_tokens": 1500,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    try:
        resp = requests.post(
            f"{base}/chat/completions", headers=headers, json=payload, timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.warning("llm_router: %s call failed: %s", base, e)
        return None


def chat(messages: list[dict], *, json_mode: bool = False,
         timeout: int = DEFAULT_TIMEOUT_S, prefer: str = "local") -> dict | None:
    """Call the routed LLM. Returns the raw OpenAI-compatible response dict
    or None when both backends fail."""
    candidates: list[tuple[str, tuple[str, str, str]]] = []
    local = _local_endpoint()
    remote = _openai_endpoint()
    if prefer == "local":
        if local: candidates.append(("local", local))
        if remote: candidates.append(("openai", remote))
    else:
        if remote: candidates.append(("openai", remote))
        if local: candidates.append(("local", local))

    for label, (base, model, key) in candidates:
        out = _post_chat(base, model, key, messages,
                         json_mode=json_mode, timeout=timeout)
        if out is not None:
            out.setdefault("_router", {})["served_by"] = label
            return out
    return None


def parse_json_content(payload: dict | None) -> dict | None:
    """Convenience for callers that asked for `json_mode`."""
    if not payload:
        return None
    try:
        text = payload["choices"][0]["message"].get("content") or ""
        return json.loads(text)
    except Exception as e:
        logger.warning("llm_router: parse failed: %s", e)
        return None
