"""Platform-Admin (Control Center) forms for Library Management — Phase 19.0E.

Narrow, safe ModelForms: each whitelists only the fields a non-technical
admin should edit. None use ``fields = "__all__"``. Publishing and copyright
clearance are deliberately handled by explicit actions / fields here, never by
a student-facing form.
"""
from __future__ import annotations

from django import forms

from .models import Book, NovelIllustration, NovelSegment, NovelVocabularyHighlight


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
