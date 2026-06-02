from __future__ import annotations

import json
import logging
import re

import requests
from django.conf import settings
from django.db.models import Case, F, IntegerField, Q, Value, When

from .models import DictionaryEntry


logger = logging.getLogger(__name__)


def _detect_lang(q: str) -> str:
    if re.search(r"[\u0600-\u06FF]", q):
        return "ar"
    return "en"


def search(query: str, lang_hint: str = "auto"):
    q = (query or "").strip().lower()
    if not q:
        return []

    lang = _detect_lang(q) if lang_hint == "auto" else lang_hint

    if lang == "ar":
        qs = DictionaryEntry.objects.filter(Q(arabic__icontains=q))
        rank = Case(
            When(arabic__iexact=q, then=Value(0)),
            When(arabic__istartswith=q, then=Value(1)),
            default=Value(2),
            output_field=IntegerField(),
        )
        qs = qs.annotate(rank=rank).order_by("rank", "-lookup_count", "arabic")
    else:
        qs = DictionaryEntry.objects.filter(Q(english__icontains=q))
        rank = Case(
            When(english__iexact=q, then=Value(0)),
            When(english__istartswith=q, then=Value(1)),
            default=Value(2),
            output_field=IntegerField(),
        )
        qs = qs.annotate(rank=rank).order_by("rank", "-lookup_count", "english")

    results = list(qs[:20])
    if results:
        DictionaryEntry.objects.filter(id__in=[e.id for e in results]).update(lookup_count=F("lookup_count") + 1)
    return results


AI_TOOL = {
    "type": "function",
    "function": {
        "name": "dictionary_entry",
        "description": "Return a bilingual dictionary entry.",
        "parameters": {
            "type": "object",
            "properties": {
                "english": {"type": "string"},
                "arabic": {"type": "string"},
                "pos": {"type": "string"},
                "example_en": {"type": "string"},
                "example_ar": {"type": "string"},
            },
            "required": ["english", "arabic", "pos", "example_en", "example_ar"],
            "additionalProperties": False,
        },
    },
}


def ai_lookup(query: str, lang_hint: str):
    q = (query or "").strip()
    if not q or not settings.AI_API_KEY:
        return None

    system = (
        "You are a bilingual Arabic ↔ English dictionary. "
        "Return exactly one JSON object via the dictionary_entry tool with: "
        "english, arabic, pos, example_en, example_ar. Keep examples short."
    )
    user = f"Lookup: {q} (hint: {lang_hint})"

    payload = {
        "model": settings.AI_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "tools": [AI_TOOL],
        "tool_choice": {"type": "function", "function": {"name": "dictionary_entry"}},
    }

    try:
        # Centralised ai_usage wrapper (Prompt 12A) meters + logs this call.
        from ai_usage import constants as AC
        from ai_usage.services import ai_client

        data = ai_client.chat(
            payload["messages"], feature=AC.FEATURE_VOCABULARY,
            model=settings.AI_MODEL,
            extra_payload={"tools": payload["tools"],
                           "tool_choice": payload["tool_choice"]},
            timeout=30,
        )
        tool_call = data["choices"][0]["message"]["tool_calls"][0]
        args = json.loads(tool_call["function"]["arguments"])

        for k in ("english", "arabic", "pos", "example_en", "example_ar"):
            if k not in args:
                raise ValueError(f"missing key {k}")

        entry, _ = DictionaryEntry.objects.get_or_create(
            english=args["english"].strip(),
            arabic=args["arabic"].strip(),
            defaults={
                "pos": (args.get("pos") or "").strip()[:20],
                "example_en": (args.get("example_en") or "").strip()[:300],
                "example_ar": (args.get("example_ar") or "").strip()[:300],
                "source": "ai",
            },
        )
        return entry
    except Exception as e:
        logger.exception("AI dictionary lookup failed: %s", e)
        return None

