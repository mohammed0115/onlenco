"""Quality + privacy + normalisation filter for training examples.

Each candidate dict goes through:
    1. Strip private data (PII) — emails, phones, IPs, tokens, URLs.
    2. Strip technical tokens (HTML, code blocks, unresolved placeholders).
    3. Normalise CEFR level (uppercase) and grammar topic.
    4. Reject empty / too-short text fields.
    5. Reject below quality threshold.
    6. Compute deterministic content_hash for dedup.

Returns a `(cleaned_dict | None, reasons: list[str])` so the caller can
keep stats (rejected, private-data, duplicates) for the QualityReport.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from accounts.models import CEFR_CHOICES

# ---- PII patterns -------------------------------------------------------

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE_RE = re.compile(
    r"(?<!\d)(?:\+?\d{1,3}[ \-.]?)?(?:\(\d{1,4}\)[ \-.]?)?"
    r"\d{3}[ \-.]?\d{3,4}[ \-.]?\d{2,4}(?!\d)"
)
_URL_RE = re.compile(r"https?://\S+|www\.\S+")
_IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_TOKEN_RE = re.compile(
    r"\b(?:sk|pk|gh[pous])_[A-Za-z0-9_-]{16,}\b"      # OpenAI / GitHub style
    r"|\b[A-Za-z0-9_-]{32,}\b"                         # generic 32+ char tokens
)
_CC_RE = re.compile(r"\b(?:\d[ -]?){13,16}\b")        # credit-card-ish

# ---- Technical-token patterns ------------------------------------------

_CODE_FENCE_RE = re.compile(r"```[\s\S]*?```")
_INLINE_CODE_RE = re.compile(r"`[^`\n]{1,100}`")
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_PLACEHOLDER_RE = re.compile(r"\{\{[^{}]+\}\}|\{%[^{}]+%\}")
_BLANK_RUN_RE = re.compile(
    r"\b(?:blank|null|none|undefined)(?:[\s\-_]+(?:blank|null|none|undefined)){1,}\b",
    re.IGNORECASE,
)

# ---- Offensive content -------------------------------------------------

_OFFENSIVE_RE = re.compile(r"\b(?:fuck|shit|bitch|asshole)\b", re.IGNORECASE)

# ---- Misc --------------------------------------------------------------

_WS_RE = re.compile(r"\s+")
_VALID_CEFR = {c[0] for c in CEFR_CHOICES}

REASON_TOO_SHORT      = "too_short"
REASON_PRIVATE_DATA   = "private_data"
REASON_TECH_TOKEN     = "technical_token"
REASON_OFFENSIVE      = "offensive"
REASON_INVALID_CEFR   = "invalid_cefr"
REASON_LOW_QUALITY    = "low_quality"
REASON_EMPTY_OUTPUT   = "empty_output"


def _redact_pii(text: str) -> tuple[str, bool]:
    """Replace PII with `[REDACTED]`. Returns (cleaned, had_pii)."""
    if not text:
        return text, False
    original = text
    text = _EMAIL_RE.sub("[REDACTED-EMAIL]", text)
    text = _URL_RE.sub("[REDACTED-URL]", text)
    text = _IPV4_RE.sub("[REDACTED-IP]", text)
    text = _TOKEN_RE.sub("[REDACTED-TOKEN]", text)
    text = _CC_RE.sub("[REDACTED-CC]", text)
    text = _PHONE_RE.sub("[REDACTED-PHONE]", text)
    return text, text != original


def _has_technical_token(text: str) -> bool:
    if not text:
        return False
    return bool(
        _CODE_FENCE_RE.search(text)
        or _HTML_TAG_RE.search(text)
        or _PLACEHOLDER_RE.search(text)
        or _BLANK_RUN_RE.search(text)
    )


def _normalise_text(text: str) -> str:
    if not text:
        return ""
    return _WS_RE.sub(" ", text).strip()


def _normalise_cefr(value: Any) -> str:
    if not value:
        return ""
    s = str(value).strip().upper()
    return s if s in _VALID_CEFR else ""


def _walk_strings(payload: Any, fn):
    """Apply `fn(str) -> (str, *)` to every string leaf inside payload.
    Returns (transformed_payload, any_changed: bool)."""
    if isinstance(payload, str):
        new, changed = fn(payload)
        return new, bool(changed)
    if isinstance(payload, list):
        out, changed = [], False
        for item in payload:
            new_item, item_changed = _walk_strings(item, fn)
            out.append(new_item)
            changed = changed or item_changed
        return out, changed
    if isinstance(payload, dict):
        out, changed = {}, False
        for k, v in payload.items():
            new_v, item_changed = _walk_strings(v, fn)
            out[k] = new_v
            changed = changed or item_changed
        return out, changed
    return payload, False


def compute_content_hash(task_type: str, input_: dict, output_: dict) -> str:
    payload = json.dumps(
        {"t": task_type, "i": input_, "o": output_},
        sort_keys=True, ensure_ascii=False,
    )
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


# ---- Public surface ----------------------------------------------------

def clean_and_filter(
    example: dict, *,
    min_quality: int = 0,
    require_cefr: bool = False,
) -> tuple[dict | None, list[str]]:
    """Return (cleaned_example, reasons).

    `cleaned_example` is None when the example must be discarded;
    otherwise it carries:
        - normalised text everywhere,
        - PII redacted,
        - `content_hash` filled in,
        - `quality_score` clipped to [0, 100],
        - `cefr_level` upper-cased.
    """
    reasons: list[str] = []
    ex = dict(example)  # shallow copy — we'll rebuild input/output

    # Normalise CEFR.
    cefr_in = ex.get("cefr_level") or ""
    cefr_norm = _normalise_cefr(cefr_in)
    if cefr_in and not cefr_norm:
        reasons.append(REASON_INVALID_CEFR)
        return None, reasons
    ex["cefr_level"] = cefr_norm
    if require_cefr and not cefr_norm:
        reasons.append(REASON_INVALID_CEFR)
        return None, reasons

    # Strings inside input/output: normalise whitespace, redact PII,
    # reject technical tokens / offensive content / empty outputs.
    pii_hit = [False]

    def _clean(s: str):
        s = _normalise_text(s)
        s, had = _redact_pii(s)
        if had:
            pii_hit[0] = True
        return s, had

    cleaned_input, _ = _walk_strings(ex.get("input") or {}, _clean)
    cleaned_output, _ = _walk_strings(ex.get("output") or {}, _clean)
    ex["input"] = cleaned_input
    ex["output"] = cleaned_output

    # Reject offensive / technical-token content anywhere in input or output.
    flat = json.dumps([cleaned_input, cleaned_output], ensure_ascii=False)
    if _OFFENSIVE_RE.search(flat):
        reasons.append(REASON_OFFENSIVE)
        return None, reasons
    if _has_technical_token(flat):
        reasons.append(REASON_TECH_TOKEN)
        return None, reasons

    # Reject if input or output strings are vacuous.
    if not _has_meaningful_text(cleaned_input):
        reasons.append(REASON_TOO_SHORT)
        return None, reasons
    if not _has_meaningful_text(cleaned_output):
        reasons.append(REASON_EMPTY_OUTPUT)
        return None, reasons

    # Quality threshold.
    score = int(ex.get("quality_score") or 0)
    score = max(0, min(100, score))
    ex["quality_score"] = score
    if score < min_quality:
        reasons.append(REASON_LOW_QUALITY)
        return None, reasons

    if pii_hit[0]:
        reasons.append(REASON_PRIVATE_DATA)

    # Stamp content_hash.
    ex["content_hash"] = compute_content_hash(
        ex.get("task_type") or "",
        cleaned_input, cleaned_output,
    )
    return ex, reasons


def _has_meaningful_text(payload: Any, *, min_chars: int = 3) -> bool:
    """True if the payload has at least one string with `min_chars`+
    non-space characters."""
    if isinstance(payload, str):
        return len(payload.strip()) >= min_chars
    if isinstance(payload, list):
        return any(_has_meaningful_text(x, min_chars=min_chars) for x in payload)
    if isinstance(payload, dict):
        return any(_has_meaningful_text(v, min_chars=min_chars) for v in payload.values())
    return False
