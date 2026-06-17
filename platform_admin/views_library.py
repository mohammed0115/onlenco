"""Platform Admin — Library Management (Phase 19.0E).

A custom Control-Center UI (NOT Django admin) for non-technical admins to
review/publish library books, chapters, segments, vocabulary and
illustrations. Read gated by CAP_LIBRARY_VIEW; mutations by CAP_LIBRARY_MANAGE.
Publishing always goes through library.services.publishing.can_publish_book.
"""
from __future__ import annotations

from django.contrib import messages
from django.db.models import Count, Q
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from library.forms import (
    PlatformBookReviewForm, PlatformChapterAudioUploadForm,
    PlatformIllustrationReviewForm, PlatformNovelImportMetadataForm,
    PlatformNovelImportUploadForm, PlatformSegmentReviewForm,
    PlatformVocabularyReviewForm,
)
from library.models import (
    Book, Chapter, LibraryImportJob, NovelIllustration, NovelSegment,
    NovelVocabularyHighlight,
)
from library.services import novel_importer
from library.services.publishing import can_publish_book

from . import permissions as perms
from .decorators import control_permission_required
from .views import _paginate, _render


def _can_manage(request) -> bool:
    return perms.can_mutate(request.user, perms.CAP_LIBRARY_MANAGE)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@control_permission_required(perms.CAP_LIBRARY_VIEW)
def library_dashboard(request):
    stats = {
        "total_books": Book.objects.count(),
        "published_books": Book.objects.filter(is_published=True).count(),
        "draft_books": Book.objects.filter(is_published=False).count(),
        "needs_copyright": Book.objects.filter(
            Q(is_copyright_cleared=False) | Q(copyright_status="unknown")).count(),
        "copyright_cleared": Book.objects.filter(is_copyright_cleared=True).count(),
        "total_chapters": Chapter.objects.count(),
        "total_segments": NovelSegment.objects.count(),
        "published_segments": NovelSegment.objects.filter(is_published=True).count(),
        "total_vocab": NovelVocabularyHighlight.objects.count(),
        "active_vocab": NovelVocabularyHighlight.objects.filter(is_active=True).count(),
        "illustrations_pending": NovelIllustration.objects.exclude(
            generation_status="approved").count(),
        "illustrations_approved": NovelIllustration.objects.filter(
            generation_status="approved").count(),
    }
    total_chapters = stats["total_chapters"]
    missing_audio = Chapter.objects.filter(audio_url="").filter(
        Q(audio_file="") | Q(audio_file__isnull=True)).count()
    stats["chapters_with_audio"] = total_chapters - missing_audio
    stats["chapters_missing_audio"] = missing_audio
    # Novel Import Wizard counters (Phase 19.0I).
    stats["import_jobs"] = LibraryImportJob.objects.count()
    stats["import_failed"] = LibraryImportJob.objects.filter(status="failed").count()
    stats["import_needs_ocr"] = LibraryImportJob.objects.filter(needs_ocr=True).count()
    stats["import_hidden_books"] = LibraryImportJob.objects.filter(
        created_book__isnull=False, created_book__is_published=False).count()
    return _render(request, "platform_admin/library/dashboard.html",
                   {"stats": stats, "section": "library"})


# ---------------------------------------------------------------------------
# Books list
# ---------------------------------------------------------------------------

@control_permission_required(perms.CAP_LIBRARY_VIEW)
def library_books(request):
    qs = Book.objects.all().order_by("title").annotate(
        chapters_count=Count("chapters", distinct=True),
        segments_count=Count("chapters__segments", distinct=True),
        pub_segments_count=Count(
            "chapters__segments",
            filter=Q(chapters__segments__is_published=True), distinct=True),
        import_job_count=Count("import_jobs", distinct=True),
    )
    f = request.GET
    if f.get("copyright_status"):
        qs = qs.filter(copyright_status=f["copyright_status"])
    if f.get("cleared") in ("0", "1"):
        qs = qs.filter(is_copyright_cleared=(f["cleared"] == "1"))
    if f.get("published") in ("0", "1"):
        qs = qs.filter(is_published=(f["published"] == "1"))
    if f.get("school") in ("0", "1"):
        qs = qs.filter(is_school_curriculum=(f["school"] == "1"))
    if f.get("country"):
        qs = qs.filter(school_country__icontains=f["country"])
    if f.get("level"):
        qs = qs.filter(target_cefr_level=f["level"])
    q = (f.get("q") or "").strip()
    if q:
        qs = qs.filter(
            Q(title__icontains=q) | Q(source_title__icontains=q)
            | Q(school_stage__icontains=q) | Q(curriculum_notes__icontains=q))

    page = _paginate(request, qs)
    return _render(request, "platform_admin/library/books.html", {
        "page_obj": page, "rows": page.object_list, "filters": f,
        "copyright_choices": Book._meta.get_field("copyright_status").choices,
        "section": "library",
    })


# ---------------------------------------------------------------------------
# Book review / edit + publish gate
# ---------------------------------------------------------------------------

@control_permission_required(perms.CAP_LIBRARY_VIEW)
def library_book_detail(request, pk):
    book = get_object_or_404(Book, pk=pk)
    if request.method == "POST":
        if not _can_manage(request):
            return HttpResponseForbidden("Forbidden")
        form = PlatformBookReviewForm(request.POST, instance=book)
        if form.is_valid():
            form.save()
            messages.success(request, "Book updated.")
            return redirect("platform_admin:library_book", pk=book.pk)
        messages.error(request, "Please fix the errors below.")
    else:
        form = PlatformBookReviewForm(instance=book)

    chapters = (
        book.chapters.all().order_by("sort_order", "id")
        .prefetch_related("segments__vocabulary_highlights", "segments__illustrations")
        .annotate(
            segments_count=Count("segments", distinct=True),
            pub_segments_count=Count(
                "segments", filter=Q(segments__is_published=True), distinct=True),
        )
    )
    return _render(request, "platform_admin/library/book_detail.html", {
        "book": book, "form": form, "chapters": chapters,
        "publish_check": can_publish_book(book),
        "can_manage": _can_manage(request), "section": "library",
    })


@require_POST
@control_permission_required(perms.CAP_LIBRARY_VIEW)
def library_book_action(request, pk, action):
    book = get_object_or_404(Book, pk=pk)
    if not _can_manage(request):
        return HttpResponseForbidden("Forbidden")
    if action == "publish":
        check = can_publish_book(book)
        if not check.allowed:
            for reason in check.reasons:
                messages.error(request, reason)
            messages.warning(request, "Book NOT published — resolve the issues above.")
        else:
            book.is_published = True
            book.save(update_fields=["is_published"])
            messages.success(request, "Book published to students.")
    elif action == "unpublish":
        book.is_published = False
        book.save(update_fields=["is_published"])
        messages.success(request, "Book hidden from students.")
    else:
        messages.error(request, "Unknown action.")
    return redirect("platform_admin:library_book", pk=book.pk)


# ---------------------------------------------------------------------------
# Segment review / edit (+ vocabulary + illustrations on the same page)
# ---------------------------------------------------------------------------

@control_permission_required(perms.CAP_LIBRARY_VIEW)
def library_segment_edit(request, pk):
    segment = get_object_or_404(
        NovelSegment.objects.select_related("chapter", "chapter__book"), pk=pk)
    if request.method == "POST":
        if not _can_manage(request):
            return HttpResponseForbidden("Forbidden")
        form = PlatformSegmentReviewForm(request.POST, instance=segment)
        if form.is_valid():
            form.save()
            messages.success(request, "Segment updated.")
            return redirect("platform_admin:library_segment", pk=segment.pk)
        messages.error(request, "Please fix the errors below.")
    else:
        form = PlatformSegmentReviewForm(instance=segment)

    return _render(request, "platform_admin/library/segment_edit.html", {
        "segment": segment, "book": segment.chapter.book, "form": form,
        "vocab": segment.vocabulary_highlights.all().order_by("order", "id"),
        "illustrations": segment.illustrations.all().order_by("order", "id"),
        "can_manage": _can_manage(request), "section": "library",
    })


@require_POST
@control_permission_required(perms.CAP_LIBRARY_VIEW)
def library_vocab_edit(request, pk):
    vocab = get_object_or_404(
        NovelVocabularyHighlight.objects.select_related("segment"), pk=pk)
    if not _can_manage(request):
        return HttpResponseForbidden("Forbidden")
    form = PlatformVocabularyReviewForm(request.POST, instance=vocab)
    if form.is_valid():
        form.save()
        messages.success(request, f"Vocabulary '{vocab.word}' updated.")
    else:
        messages.error(request, "Could not update the vocabulary item.")
    return redirect("platform_admin:library_segment", pk=vocab.segment_id)


@require_POST
@control_permission_required(perms.CAP_LIBRARY_VIEW)
def library_illustration_edit(request, pk):
    illustration = get_object_or_404(
        NovelIllustration.objects.select_related("segment"), pk=pk)
    if not _can_manage(request):
        return HttpResponseForbidden("Forbidden")
    form = PlatformIllustrationReviewForm(request.POST, instance=illustration)
    if form.is_valid():
        form.save()
        messages.success(request, "Illustration updated.")
    else:
        messages.error(request, "Could not update the illustration.")
    return redirect("platform_admin:library_segment", pk=illustration.segment_id)


# ---------------------------------------------------------------------------
# Chapter audio upload (Phase 19.0F) — admin uploads a per-chapter recording.
# ---------------------------------------------------------------------------

@control_permission_required(perms.CAP_LIBRARY_VIEW)
def library_chapter_audio(request, pk):
    chapter = get_object_or_404(Chapter.objects.select_related("book"), pk=pk)
    if request.method == "POST":
        if not _can_manage(request):
            return HttpResponseForbidden("Forbidden")
        form = PlatformChapterAudioUploadForm(request.POST, request.FILES, instance=chapter)
        if form.is_valid():
            form.save()
            messages.success(request, "Chapter audio uploaded.")
            return redirect("platform_admin:library_chapter_audio", pk=chapter.pk)
        messages.error(request, "Upload failed — please check the file.")
    else:
        form = PlatformChapterAudioUploadForm(instance=chapter)
    return _render(request, "platform_admin/library/chapter_audio.html", {
        "chapter": chapter, "book": chapter.book, "form": form,
        "can_manage": _can_manage(request), "section": "library",
    })


@control_permission_required(perms.CAP_LIBRARY_VIEW)
def library_chapter_audio_preview(request, pk):
    """Staff-only preview of an uploaded recording (Phase 19.0G).

    Streams the file through the secure delivery helper instead of exposing
    the raw MEDIA_URL in the admin page. Gated by CAP_LIBRARY_VIEW only —
    no student subscription / session is required for staff preview.
    """
    chapter = get_object_or_404(Chapter, pk=pk)
    if not chapter.audio_file:
        raise Http404("No chapter recording")
    from library.services.audio_delivery import audio_file_response
    return audio_file_response(chapter.audio_file)


@require_POST
@control_permission_required(perms.CAP_LIBRARY_VIEW)
def library_chapter_audio_remove(request, pk):
    chapter = get_object_or_404(Chapter, pk=pk)
    if not _can_manage(request):
        return HttpResponseForbidden("Forbidden")
    if chapter.audio_file:
        chapter.audio_file.delete(save=False)  # remove the stored file
    chapter.audio_file = None
    chapter.duration_seconds = 0
    chapter.save(update_fields=["audio_file", "duration_seconds"])
    messages.success(request, "Chapter audio removed.")
    return redirect("platform_admin:library_chapter_audio", pk=chapter.pk)


# ---------------------------------------------------------------------------
# Novel Import Wizard (Phase 19.0I)
#
# upload → analyze (dry-run) → apply (creates a HIDDEN book). Never publishes,
# never generates translation/vocab/audio, never runs OCR (detection only).
# ---------------------------------------------------------------------------

@control_permission_required(perms.CAP_LIBRARY_VIEW)
def library_imports(request):
    """List import jobs (view-gated). Upload/apply still need manage."""
    qs = LibraryImportJob.objects.select_related("uploaded_by", "created_book")
    page = _paginate(request, qs)
    return _render(request, "platform_admin/library/imports_list.html", {
        "page_obj": page, "rows": page.object_list,
        "can_manage": _can_manage(request), "section": "library",
    })


@control_permission_required(perms.CAP_LIBRARY_VIEW)
def library_import_new(request):
    """Upload a new novel source. POST requires manage."""
    if request.method == "POST":
        if not _can_manage(request):
            return HttpResponseForbidden("Forbidden")
        form = PlatformNovelImportUploadForm(request.POST, request.FILES)
        if form.is_valid():
            import os
            job = form.save(commit=False)
            job.uploaded_by = request.user
            up = form.cleaned_data["source_file"]
            job.original_filename = os.path.basename(getattr(up, "name", "") or "")
            job.source_format = novel_importer.source_format(job.original_filename)
            job.status = "uploaded"
            job.save()
            messages.success(request, "Source uploaded. Run Analyze to preview.")
            return redirect("platform_admin:library_import", pk=job.pk)
        messages.error(request, "Upload failed — please check the file.")
    else:
        form = PlatformNovelImportUploadForm()
    return _render(request, "platform_admin/library/import_new.html", {
        "form": form, "can_manage": _can_manage(request), "section": "library",
    })


@control_permission_required(perms.CAP_LIBRARY_VIEW)
def library_import_detail(request, pk):
    job = get_object_or_404(LibraryImportJob.objects.select_related("created_book"), pk=pk)
    # Pre-fill metadata from analysis (title guess = original filename stem).
    import os
    title_guess = os.path.splitext(job.original_filename or "")[0].replace("_", " ").strip()
    meta_form = PlatformNovelImportMetadataForm(initial={"title": title_guess})
    return _render(request, "platform_admin/library/import_detail.html", {
        "job": job, "meta_form": meta_form,
        "can_manage": _can_manage(request), "section": "library",
    })


@require_POST
@control_permission_required(perms.CAP_LIBRARY_VIEW)
def library_import_analyze(request, pk):
    """Dry-run: inspect the source and store metadata. Writes NO Book."""
    if not _can_manage(request):
        return HttpResponseForbidden("Forbidden")
    job = get_object_or_404(LibraryImportJob, pk=pk)
    if job.status == "imported":
        messages.warning(request, "This job was already imported.")
        return redirect("platform_admin:library_import", pk=job.pk)
    if not job.source_file:
        messages.error(request, "No source file on this job.")
        return redirect("platform_admin:library_import", pk=job.pk)
    try:
        result = novel_importer.analyze_source(job.source_file.path)
    except novel_importer.NovelImportError as exc:
        job.status = "failed"
        job.errors = [str(exc)]  # clean message only — never a raw traceback
        job.save(update_fields=["status", "errors", "updated_at"])
        messages.error(request, f"Analyze failed: {exc}")
        return redirect("platform_admin:library_import", pk=job.pk)
    job.page_count = result["page_count"]
    job.word_count = result["word_count"]
    job.chapter_count = result["chapter_count"]
    job.segment_count = result["segment_count"]
    job.detected_text_layer = result["detected_text_layer"]
    job.needs_ocr = result["needs_ocr"]
    job.warnings = result["warnings"]
    job.errors = []
    job.preview = {
        "first_chapter_titles": result["first_chapter_titles"],
        "first_segment_preview": result["first_segment_preview"],
        "format": result["format"],
    }
    job.status = "analyzed"
    job.save()
    messages.success(request, "Analysis complete — review, then Import.")
    return redirect("platform_admin:library_import", pk=job.pk)


@require_POST
@control_permission_required(perms.CAP_LIBRARY_VIEW)
def library_import_apply(request, pk):
    """Create a HIDDEN Book/Chapters/Segments from the job. Idempotent."""
    if not _can_manage(request):
        return HttpResponseForbidden("Forbidden")
    job = get_object_or_404(LibraryImportJob, pk=pk)
    if job.status == "imported" or job.created_book_id:
        messages.warning(request, "This job has already been imported.")
        return redirect("platform_admin:library_import", pk=job.pk)
    if not job.source_file:
        messages.error(request, "No source file on this job.")
        return redirect("platform_admin:library_import", pk=job.pk)
    meta_form = PlatformNovelImportMetadataForm(request.POST)
    if not meta_form.is_valid():
        messages.error(request, "Please fix the metadata before importing.")
        return _render(request, "platform_admin/library/import_detail.html", {
            "job": job, "meta_form": meta_form,
            "can_manage": _can_manage(request), "section": "library",
        })
    metadata = {k: meta_form.cleaned_data[k] for k in meta_form.cleaned_data}
    try:
        result = novel_importer.import_novel(job.source_file.path, metadata=metadata)
    except novel_importer.NovelImportError as exc:
        job.status = "failed"
        job.errors = [str(exc)]  # clean message only
        job.save(update_fields=["status", "errors", "updated_at"])
        messages.error(request, f"Import failed: {exc}")
        return redirect("platform_admin:library_import", pk=job.pk)
    job.created_book_id = result["book_id"]
    job.status = "imported"
    job.errors = []
    job.save(update_fields=["created_book", "status", "errors", "updated_at"])
    messages.success(
        request,
        f"Imported '{result['book_title']}' (hidden from students) — "
        f"{result['chapters_created']} chapters, {result['segments_created']} segments.",
    )
    return redirect("platform_admin:library_book", pk=result["book_id"])
