"""Platform-Admin (Control Center) forms for Library Management — Phase 19.0E.

Narrow, safe ModelForms: each whitelists only the fields a non-technical
admin should edit. None use ``fields = "__all__"``. Publishing and copyright
clearance are deliberately handled by explicit actions / fields here, never by
a student-facing form.
"""
from __future__ import annotations

import os

from django import forms
from django.conf import settings

from .models import (
    Book, Chapter, NovelIllustration, NovelSegment, NovelVocabularyHighlight,
)

# Allowed audio uploads for chapter-level recordings (Phase 19.0F).
CHAPTER_AUDIO_EXTENSIONS = (".mp3", ".wav", ".m4a")
CHAPTER_AUDIO_CONTENT_TYPES = {
    "audio/mpeg", "audio/mp3", "audio/wav", "audio/x-wav", "audio/wave",
    "audio/mp4", "audio/x-m4a", "audio/m4a", "application/octet-stream",
}


class PlatformBookReviewForm(forms.ModelForm):
    """Edit a book's metadata + copyright fields. Does NOT include is_published
    (publishing goes through the publish gate/action)."""

    class Meta:
        model = Book
        fields = [
            "title", "summary",
            "copyright_status", "source_title", "source_url", "license_notes",
            "is_copyright_cleared", "content_language", "target_cefr_level",
            "is_school_curriculum", "school_country", "school_stage",
            "curriculum_notes",
        ]

    def clean_title(self):
        title = (self.cleaned_data.get("title") or "").strip()
        if not title:
            raise forms.ValidationError("Title cannot be empty.")
        return title


class PlatformSegmentReviewForm(forms.ModelForm):
    """Edit one novel segment. Refuses to publish a segment with empty text."""

    class Meta:
        model = NovelSegment
        fields = [
            "title", "text_en", "text_ar", "arabic_summary", "cefr_level",
            "estimated_reading_seconds", "estimated_audio_seconds", "is_published",
        ]

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("is_published") and not (cleaned.get("text_en") or "").strip():
            self.add_error(
                "is_published",
                "Cannot publish a segment that has empty English text.")
        return cleaned


class PlatformVocabularyReviewForm(forms.ModelForm):
    """Manual review/edit of one vocabulary highlight (no generation)."""

    class Meta:
        model = NovelVocabularyHighlight
        fields = ["meaning_ar", "explanation_ar", "example_sentence", "cefr_level", "is_active"]


class PlatformIllustrationReviewForm(forms.ModelForm):
    """Edit safe presentation fields of an illustration. Does NOT change the
    generation_status / image — that stays in the media-review lifecycle so
    pending/rejected images can never be flipped student-visible from here."""

    class Meta:
        model = NovelIllustration
        fields = ["alt_text", "order"]


class PlatformChapterAudioUploadForm(forms.ModelForm):
    """Upload/replace a chapter-level audio recording from Platform Admin.

    Accepts only .mp3 / .wav / .m4a within the configured size limit. Never
    touches copyright/publish flags or any other field.
    """

    duration_seconds = forms.IntegerField(
        required=False, min_value=0,
        help_text="Optional — length in seconds (for filtering/UI).")

    class Meta:
        model = Chapter
        fields = ["audio_file", "duration_seconds"]

    def clean_audio_file(self):
        f = self.cleaned_data.get("audio_file")
        if not f:
            raise forms.ValidationError("Please choose an audio file.")
        # Extension (also blocks path traversal — only the basename's ext matters).
        name = os.path.basename(getattr(f, "name", "") or "")
        ext = os.path.splitext(name)[1].lower()
        if ext not in CHAPTER_AUDIO_EXTENSIONS:
            raise forms.ValidationError(
                "Only .mp3, .wav or .m4a audio files are allowed.")
        # Size limit.
        max_mb = int(getattr(settings, "LIBRARY_CHAPTER_AUDIO_MAX_MB", 100) or 100)
        if getattr(f, "size", 0) > max_mb * 1024 * 1024:
            raise forms.ValidationError(f"File is too large (max {max_mb} MB).")
        # Content type (best-effort; some browsers send octet-stream).
        ctype = (getattr(f, "content_type", "") or "").lower()
        if ctype and ctype not in CHAPTER_AUDIO_CONTENT_TYPES:
            raise forms.ValidationError("That file does not look like an audio file.")
        return f

    def clean_duration_seconds(self):
        return self.cleaned_data.get("duration_seconds") or 0
