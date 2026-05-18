"""Library Natural Reader — pre-TTS text preparation.

This sits on top of ``humanize_for_speech``: that layer already handles
markdown / placeholders / snake_case / URLs. The book-reading path adds
the concerns that only matter for *long-form* TTS:

  * **Abbreviation expansion** — "UAE" → "U.A.E." (dotted spelling forces
    TTS engines to spell-out instead of pronouncing as "you-ay-ee" or
    one mumbled syllable).
  * **Stronger symbol stripping** — underscores between letters, leftover
    asterisks, repeated punctuation should never reach the engine.
  * **Pause hints** — long paragraphs are split on sentence boundaries
    so the engine breathes naturally.
  * **Chunking** — OpenAI ``/audio/speech`` rejects >4096 chars; we slice
    on sentence boundaries to ~3500 chars per chunk.

Public:
    prepare_for_reading(text, language="en") -> dict
        {"tts_ready_text", "chunks", "original_chars", "tts_chars",
         "applied_rules": [...]}
"""
from __future__ import annotations

import re
from typing import Iterable

from .text_humanizer import humanize_for_speech


# Hard upper bound for a single TTS request. OpenAI /audio/speech caps at
# 4096; we leave headroom for prefix/suffix tokens the engine may inject.
TTS_CHUNK_LIMIT_CHARS = 3500


# ---------------------------------------------------------------------------
# Abbreviation glossary
# ---------------------------------------------------------------------------
#
# Each entry maps an *uppercase* abbreviation to its dotted spelling. The
# dotted form is what we feed TTS — it forces letter-by-letter speech in
# most engines (e.g. "U.A.E." is read "you ay ee", not "wəy"). For the
# subset where the *expanded form* is preferred (commonly read aloud as
# the full phrase), put the expansion directly in EXPANSIONS.

DOTTED_ABBREVIATIONS = {
    "UAE": "U.A.E.",
    "USA": "U.S.A.",
    "UK":  "U.K.",
    "US":  "U.S.",
    "EU":  "E.U.",
    "FBI": "F.B.I.",
    "CIA": "C.I.A.",
    "NASA": "N.A.S.A.",
    "GMT": "G.M.T.",
    "UTC": "U.T.C.",
    "BBC": "B.B.C.",
    "CNN": "C.N.N.",
    "PhD": "P.h.D.",
    "MBA": "M.B.A.",
    "ID":  "I.D.",
    "TV":  "T.V.",
    "CEO": "C.E.O.",
    "CTO": "C.T.O.",
}

# Expansions that are nicer read in full than spelled out.
EXPANSIONS = {
    "etc.": "et cetera",
    "etc": "et cetera",
    "i.e.": "that is,",
    "e.g.": "for example,",
    "vs.": "versus",
    "vs": "versus",
    "Mr.": "Mister",
    "Mrs.": "Misses",
    "Dr.": "Doctor",
    "St.": "Saint",
    "No.": "Number",
}


# Sentence boundary: end-of-sentence punctuation followed by whitespace
# (or end of string). Kept conservative on purpose — we'd rather under-
# split than slice in the middle of "Mr. Smith".
_SENTENCE_END_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z؀-ۿ])")

# Underscore between letters/digits is decoration in book text and would
# otherwise be read as "underscore". Replace with space; humanize_for_speech
# preserves underscores because of snake_case, so we do the book-side cleanup
# here.
_UNDERSCORE_BETWEEN_WORDS = re.compile(r"(?<=\w)_+(?=\w)")
_REPEATED_PUNCT = re.compile(r"([.!?,:;])\1+")
_LITERAL_LITERAL_SYMBOLS = re.compile(r"(?:^|\s)(?:underscore|slash|asterisk|dash|colon)(?:\s|$)", re.IGNORECASE)
_ORPHAN_ASTERISK = re.compile(r"(?<!\*)\*(?!\*)")
_SOFT_HYPHEN = re.compile("[­​‌‍]")  # invisible chars


def _expand_abbreviations(text: str) -> tuple[str, list[str]]:
    """Return ``(expanded_text, rules_applied)``."""
    applied: list[str] = []
    for short, long in EXPANSIONS.items():
        pattern = re.compile(rf"\b{re.escape(short)}", flags=re.IGNORECASE)
        before = text
        text = pattern.sub(long, text)
        if text != before:
            applied.append(f"expand:{short}")
    for short, dotted in DOTTED_ABBREVIATIONS.items():
        pattern = re.compile(rf"\b{re.escape(short)}\b")
        before = text
        text = pattern.sub(dotted, text)
        if text != before:
            applied.append(f"dotted:{short}")
    return text, applied


def _strip_book_symbols(text: str) -> tuple[str, list[str]]:
    """Decoration-only symbol cleanup for book passages."""
    applied: list[str] = []
    before = text
    text = _SOFT_HYPHEN.sub("", text)
    if text != before:
        applied.append("strip_soft_hyphen")
    before = text
    text = _UNDERSCORE_BETWEEN_WORDS.sub(" ", text)
    if text != before:
        applied.append("strip_underscores")
    before = text
    text = _ORPHAN_ASTERISK.sub("", text)
    if text != before:
        applied.append("strip_orphan_asterisks")
    before = text
    text = _REPEATED_PUNCT.sub(r"\1", text)
    if text != before:
        applied.append("collapse_repeated_punct")
    before = text
    text = _LITERAL_LITERAL_SYMBOLS.sub(" ", text)
    if text != before:
        applied.append("strip_literal_symbols")
    return text, applied


def _split_into_sentences(text: str) -> list[str]:
    parts = _SENTENCE_END_RE.split(text)
    return [p.strip() for p in parts if p.strip()]


def _chunk_for_tts(sentences: Iterable[str], limit: int = TTS_CHUNK_LIMIT_CHARS) -> list[str]:
    """Greedy chunker — packs sentences into ``limit``-char chunks.

    A sentence longer than ``limit`` is force-split at the nearest space
    so the chunk count is always finite.
    """
    chunks: list[str] = []
    current = ""
    for s in sentences:
        if len(s) > limit:
            if current:
                chunks.append(current.strip())
                current = ""
            # Force-split the long sentence.
            while len(s) > limit:
                cut = s.rfind(" ", 0, limit) or limit
                chunks.append(s[:cut].strip())
                s = s[cut:].lstrip()
            if s:
                current = s
            continue
        candidate = (current + " " + s).strip() if current else s
        if len(candidate) > limit:
            chunks.append(current.strip())
            current = s
        else:
            current = candidate
    if current.strip():
        chunks.append(current.strip())
    return chunks


def estimate_speech_duration_seconds(text: str, *, wpm: int = 155) -> int:
    """Rough duration estimate. 155 wpm is the average English audiobook
    pace. Used to deduct quota when the upstream engine doesn't return a
    duration header.
    """
    if not text:
        return 0
    words = max(1, len(text.split()))
    return int(round(words / wpm * 60))


def prepare_for_reading(text: str, language: str = "en") -> dict:
    """Run the full normalisation pipeline.

    Returns a dict with both the original-length and TTS-ready lengths so
    the caller can log the delta + present the cleaned text in admin
    review. ``chunks`` is what the caller should actually feed to TTS;
    each chunk is ≤ ``TTS_CHUNK_LIMIT_CHARS`` characters.
    """
    if not isinstance(text, str):
        text = "" if text is None else str(text)
    original = text
    applied_rules: list[str] = []

    # Empty / whitespace-only input must return empty — the tutor-style
    # "Here is an update from Onlenco" fallback in humanize_for_speech is
    # appropriate for short notifications, not book chapters.
    if not text.strip():
        return {
            "tts_ready_text": "",
            "chunks": [],
            "original_chars": len(original),
            "tts_chars": 0,
            "estimated_seconds": 0,
            "applied_rules": [],
        }

    # Step 1: base humanizer (handles markdown / placeholders / etc.)
    text = humanize_for_speech(text, language=language) or ""

    # Step 2: book-specific symbol stripping
    text, rules = _strip_book_symbols(text)
    applied_rules.extend(rules)

    # Step 3: abbreviation handling
    text, rules = _expand_abbreviations(text)
    applied_rules.extend(rules)

    # Step 4: collapse extra spaces produced by symbol stripping
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\s+\n", "\n", text).strip()

    sentences = _split_into_sentences(text)
    chunks = _chunk_for_tts(sentences)

    return {
        "tts_ready_text": text,
        "chunks": chunks,
        "original_chars": len(original),
        "tts_chars": len(text),
        "estimated_seconds": estimate_speech_duration_seconds(text),
        "applied_rules": applied_rules,
    }
