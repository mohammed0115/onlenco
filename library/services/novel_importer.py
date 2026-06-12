"""Safe import pipeline for full public-domain novels (e.g. The Black Tulip).

Design:
  * The raw source file lives OUTSIDE the repo — callers pass an absolute
    ``--source`` path. Nothing here depends on a file being inside Git.
  * Text extraction uses ``pypdf`` for ``.pdf`` and plain read for ``.txt``
    (the ``.txt`` path keeps the cleaner/detector/segmenter unit-testable
    without shipping a real PDF).
  * Cleaning / chapter-detection / segmentation operate on plain strings, so
    they are deterministic and fully testable.
  * Anything imported is NON-student-visible: the Book is created with
    ``is_published=False`` and ``is_copyright_cleared=False`` and segments
    with ``is_published=False`` — a human must review and clear before any
    publication.
"""
from __future__ import annotations

import os
import re
import unicodedata
from dataclasses import dataclass, field

from django.db import transaction


# --- Errors ----------------------------------------------------------------

class NovelImportError(Exception):
    """Base class for importer errors (clean message, no traceback needed)."""


class PdfSourceMissing(NovelImportError):
    pass


class PdfExtractionUnavailable(NovelImportError):
    pass


# --- Tunables --------------------------------------------------------------

SEGMENT_TARGET_WORDS = 120          # aim per segment
SEGMENT_MAX_WORDS = 160             # soft ceiling (never split a sentence)
READING_WPM = 200                   # silent reading speed
AUDIO_WPM = 150                     # natural TTS narration speed


# --- Roman-numeral chapter heading detection -------------------------------

_ROMAN_CHARS = set("IVXLCDM")
# A heading line: optional "CHAPTER"/"Chapter" then a roman numeral, OR a bare
# UPPERCASE roman numeral on its own line. Uppercase-only avoids matching the
# pronoun "i". Arabic "Chapter 12" is also accepted.
_HEADING_RE = re.compile(
    r"^\s*(?:CHAPTER\s+)?([IVXLCDM]{1,8})\.?\s*$"
)
_HEADING_ARABIC_NUM_RE = re.compile(r"^\s*CHAPTER\s+(\d{1,3})\.?\s*$", re.IGNORECASE)
_SENTENCE_RE = re.compile(r"[^.!?]*[.!?]+[\"')\]]*\s*", re.S)


def _roman_to_int(s: str) -> int | None:
    vals = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    total, prev = 0, 0
    for ch in reversed(s.upper()):
        v = vals.get(ch)
        if v is None:
            return None
        if v < prev:
            total -= v
        else:
            total += v
            prev = v
    return total if total > 0 else None


def _heading_number(line: str) -> int | None:
    """Return the chapter number if ``line`` is a chapter heading, else None."""
    stripped = line.strip()
    if not stripped or len(stripped) > 16:
        return None
    m = _HEADING_RE.match(stripped)
    if m and set(m.group(1).upper()) <= _ROMAN_CHARS:
        n = _roman_to_int(m.group(1))
        if n is not None and 1 <= n <= 200:
            return n
    m = _HEADING_ARABIC_NUM_RE.match(stripped)
    if m:
        return int(m.group(1))
    return None


# --- Cleaning --------------------------------------------------------------

_INVISIBLE = dict.fromkeys(
    map(ord, ["​", "‌", "‍", "﻿", "­"]), None
)


def clean_text(raw: str) -> tuple[str, list[str]]:
    """Return ``(cleaned_text, warnings)``.

    Removes null/replacement/control/invisible characters, repairs hyphenated
    line breaks, drops page-number-only lines, collapses whitespace, and
    preserves paragraph boundaries (blank line between paragraphs).
    """
    warnings: list[str] = []
    if not raw:
        return "", ["empty source text"]

    if "\x00" in raw:
        warnings.append("null characters removed")
    if "�" in raw:
        warnings.append("unicode replacement characters (\\ufffd) found — source may be lossy")

    text = unicodedata.normalize("NFKC", raw)
    # Strip null + replacement chars and zero-width/invisible chars.
    text = text.replace("\x00", "").replace("�", "")
    text = text.translate(_INVISIBLE)
    # Drop other control chars except newline/tab.
    text = "".join(
        ch for ch in text
        if ch in ("\n", "\t") or unicodedata.category(ch)[0] != "C"
    )
    # Repair hyphenation across line breaks: "exam-\nple" -> "example".
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)

    cleaned_lines: list[str] = []
    dropped_pagenums = 0
    for line in text.split("\n"):
        s = line.strip()
        if re.fullmatch(r"\d{1,4}", s):  # standalone page number
            dropped_pagenums += 1
            continue
        cleaned_lines.append(line)
    if dropped_pagenums:
        warnings.append(f"{dropped_pagenums} page-number line(s) dropped")
    text = "\n".join(cleaned_lines)

    # Collapse 3+ newlines to a paragraph break; collapse runs of spaces.
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip(), warnings


# --- Chapter detection -----------------------------------------------------

def detect_chapters(text: str, *, fallback_words: int = 1500) -> tuple[list[dict], list[str]]:
    """Split into ``[{title, number, body}]``.

    Tries roman-numeral / "Chapter N" headings; if fewer than 2 are found it
    falls back to chunking every ``fallback_words`` words so the importer is
    never fragile.
    """
    warnings: list[str] = []
    lines = text.split("\n")
    chapters: list[dict] = []
    current: dict | None = None

    for line in lines:
        n = _heading_number(line)
        if n is not None:
            current = {"number": n, "title": f"Chapter {n}", "body_lines": []}
            chapters.append(current)
            continue
        if current is not None:
            current["body_lines"].append(line)

    detected = [
        {"number": c["number"], "title": c["title"],
         "body": "\n".join(c["body_lines"]).strip()}
        for c in chapters
        if "\n".join(c["body_lines"]).strip()
    ]

    if len(detected) >= 2:
        return detected, warnings

    # Fallback — chunk by word count.
    warnings.append(
        f"chapter headings unreliable ({len(detected)} found) — "
        f"falling back to ~{fallback_words}-word chunks"
    )
    words = text.split()
    chunks: list[dict] = []
    for i in range(0, len(words), fallback_words):
        chunk = " ".join(words[i:i + fallback_words]).strip()
        if chunk:
            num = len(chunks) + 1
            chunks.append({"number": num, "title": f"Part {num}", "body": chunk})
    return chunks, warnings


# --- Segmentation ----------------------------------------------------------

def segment_text(body: str, *, target: int = SEGMENT_TARGET_WORDS,
                 maximum: int = SEGMENT_MAX_WORDS) -> list[str]:
    """Split a chapter body into segments of ~target words on sentence
    boundaries (never mid-sentence)."""
    sentences = [m.group(0).strip() for m in _SENTENCE_RE.finditer(body) if m.group(0).strip()]
    if not sentences:
        body = body.strip()
        return [body] if body else []

    segments: list[str] = []
    buf: list[str] = []
    count = 0
    for sent in sentences:
        w = len(sent.split())
        if buf and count + w > maximum:
            segments.append(" ".join(buf))
            buf, count = [], 0
        buf.append(sent)
        count += w
        if count >= target:
            segments.append(" ".join(buf))
            buf, count = [], 0
    if buf:
        segments.append(" ".join(buf))
    return segments


def estimate_seconds(word_count: int) -> tuple[int, int]:
    """Return ``(reading_seconds, audio_seconds)`` from a word count."""
    reading = round(word_count / READING_WPM * 60)
    audio = round(word_count / AUDIO_WPM * 60)
    return reading, audio


# --- Source extraction -----------------------------------------------------

def extract_source_text(path: str) -> tuple[str, int]:
    """Return ``(raw_text, page_count)`` from a ``.pdf`` or ``.txt`` source.

    Raises ``PdfSourceMissing`` if the path does not exist and
    ``PdfExtractionUnavailable`` if pypdf is needed but not installed.
    """
    if not path or not os.path.exists(path):
        raise PdfSourceMissing(
            f"Source not found: {path!r}. Pass a valid local path via --source "
            f"(source files live outside Git, e.g. under local_content_sources/)."
        )
    if path.lower().endswith(".txt"):
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read(), 0
    try:
        from pypdf import PdfReader
    except Exception as exc:  # pragma: no cover - exercised only without pypdf
        raise PdfExtractionUnavailable(
            "PDF extraction needs 'pypdf' (pip install pypdf). It is listed in "
            "requirements.txt. Provide a .txt source to import without it."
        ) from exc
    reader = PdfReader(path)
    parts = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            parts.append("")
    return "\n".join(parts), len(reader.pages)


# --- Orchestration ---------------------------------------------------------

@dataclass
class ImportPreview:
    file_exists: bool
    page_count: int
    word_count: int
    chapter_count: int
    segment_count: int
    first_chapter_titles: list[str] = field(default_factory=list)
    first_segment_preview: str = ""
    warnings: list[str] = field(default_factory=list)


def build_preview(source_path: str, *, max_chapters: int | None = None) -> ImportPreview:
    raw, page_count = extract_source_text(source_path)
    cleaned, warn1 = clean_text(raw)
    chapters, warn2 = detect_chapters(cleaned)
    if max_chapters:
        chapters = chapters[:max_chapters]

    segment_count = 0
    first_preview = ""
    for ch in chapters:
        segs = segment_text(ch["body"])
        segment_count += len(segs)
        if not first_preview and segs:
            first_preview = segs[0][:280]

    return ImportPreview(
        file_exists=True,
        page_count=page_count,
        word_count=len(cleaned.split()),
        chapter_count=len(chapters),
        segment_count=segment_count,
        first_chapter_titles=[c["title"] for c in chapters[:3]],
        first_segment_preview=first_preview,
        warnings=warn1 + warn2,
    )


BOOK_TITLE = "The Black Tulip — Full Import Review"


@transaction.atomic
def apply_import(source_path: str, *, max_chapters: int | None = None,
                 replace: bool = False) -> dict:
    """Create/refresh the review Book + Chapters + NovelSegments.

    Always NON-student-visible: ``is_published=False`` and
    ``is_copyright_cleared=False``. No illustrations or vocabulary are created.
    """
    from library.models import Book, Chapter, NovelSegment

    raw, page_count = extract_source_text(source_path)
    cleaned, _ = clean_text(raw)
    chapters, _ = detect_chapters(cleaned)
    if max_chapters:
        chapters = chapters[:max_chapters]

    if replace:
        Book.objects.filter(title=BOOK_TITLE).delete()

    book, _ = Book.objects.update_or_create(
        title=BOOK_TITLE,
        defaults={
            "author": "Alexandre Dumas (père)",
            "category": "novel",
            "level": "B2",
            "summary": "Full import of The Black Tulip for admin review. Not published.",
            "is_published": False,
            "copyright_status": "public_domain",
            "is_copyright_cleared": False,
            "source_title": "The Black Tulip",
            "source_url": "",
            "license_notes": (
                "Imported from local PDF source for admin review; not "
                "student-published until copyright is cleared."
            ),
            "content_language": "en",
            "target_cefr_level": "B2",
            "is_school_curriculum": True,
            "school_country": "Sudan",
            "school_stage": "Secondary",
            "curriculum_notes": "Full-novel import pipeline (19.0D). Review before publish.",
        },
    )

    # Refresh chapters/segments for this review book (idempotent rebuild).
    book.chapters.all().delete()

    chapters_created = 0
    segments_created = 0
    for ch_index, ch in enumerate(chapters, start=1):
        chapter = Chapter.objects.create(
            book=book, sort_order=ch_index, title=ch["title"], body="",
        )
        chapters_created += 1
        for seg_index, seg_text in enumerate(segment_text(ch["body"]), start=1):
            words = len(seg_text.split())
            reading, audio = estimate_seconds(words)
            NovelSegment.objects.create(
                chapter=chapter, order=seg_index,
                text_en=seg_text, text_ar="", arabic_summary="",
                cefr_level="B2",
                estimated_reading_seconds=reading,
                estimated_audio_seconds=audio,
                is_published=False,
            )
            segments_created += 1

    return {
        "book_id": book.pk,
        "book_title": book.title,
        "page_count": page_count,
        "chapters_created": chapters_created,
        "segments_created": segments_created,
        "is_published": book.is_published,
        "is_copyright_cleared": book.is_copyright_cleared,
    }
