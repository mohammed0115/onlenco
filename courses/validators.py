"""Safe file-upload validators for teacher-uploaded media.

Two layers:
  * Extension allowlist — fast, deterministic, blocks the obvious
    `.exe` / `.sh` cases.
  * Size cap — prevents accidental denial-of-service via 5 GB videos.

Spec rule: never accept executable uploads. The allowlists below are
the only file types Onlenco accepts; everything else raises a
`ValidationError`.
"""
from __future__ import annotations

import os

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

# Per-resource-kind extension allowlists (lower-cased, with leading dot).
ALLOWED_EXTENSIONS = {
    "video":     {".mp4", ".webm", ".m4v"},
    "audio":     {".mp3", ".wav", ".m4a", ".ogg"},
    "document":  {".pdf"},
    "image":     {".png", ".jpg", ".jpeg", ".webp", ".gif"},
    "worksheet": {".pdf", ".docx"},
}

# 250 MB ceiling on any single uploaded file. Override via settings if
# storage allows larger.
DEFAULT_MAX_BYTES = 250 * 1024 * 1024


def _ext(name: str) -> str:
    return os.path.splitext((name or "").lower())[1]


def validate_extension(file_obj, kind: str) -> None:
    """Raise `ValidationError` when the file's extension isn't in the
    allowlist for `kind`."""
    allowed = ALLOWED_EXTENSIONS.get(kind)
    if allowed is None:
        raise ValidationError(_("Unknown upload kind: %(kind)s") % {"kind": kind})
    ext = _ext(getattr(file_obj, "name", ""))
    if ext not in allowed:
        raise ValidationError(
            _("File type %(ext)s is not allowed for %(kind)s. "
              "Allowed types: %(allowed)s") % {
                "ext": ext or "(none)", "kind": kind,
                "allowed": ", ".join(sorted(allowed)),
            }
        )


def validate_size(file_obj, max_bytes: int = DEFAULT_MAX_BYTES) -> None:
    size = getattr(file_obj, "size", 0) or 0
    if size > max_bytes:
        raise ValidationError(
            _("File is too large (%(mb).1f MB). Maximum allowed is %(max).0f MB.")
            % {"mb": size / (1024 * 1024), "max": max_bytes / (1024 * 1024)}
        )


def validate_video(file_obj):
    validate_extension(file_obj, "video")
    validate_size(file_obj)


def validate_audio(file_obj):
    validate_extension(file_obj, "audio")
    validate_size(file_obj)


def validate_document(file_obj):
    validate_extension(file_obj, "document")
    validate_size(file_obj)


def validate_image(file_obj):
    validate_extension(file_obj, "image")
    validate_size(file_obj)


def validate_worksheet(file_obj):
    validate_extension(file_obj, "worksheet")
    validate_size(file_obj)


# ---------------------------------------------------------------------------
# Video URL parsing — recognise the providers we accept on Lesson.video_url:
# YouTube, Vimeo, or a direct .mp4/.webm link.
# ---------------------------------------------------------------------------

import re
from urllib.parse import urlparse, parse_qs

_YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "www.youtu.be"}
_VIMEO_HOSTS   = {"vimeo.com", "www.vimeo.com", "player.vimeo.com"}
_DIRECT_VIDEO_RE = re.compile(r"\.(mp4|webm|m4v)(\?|$)", re.IGNORECASE)


def parse_video_url(url: str) -> dict | None:
    """Identify a video URL and return its provider + canonical id/url.

    Returns dict with `kind` ∈ {"youtube", "vimeo", "direct"} on success,
    or None if the URL doesn't match any accepted provider. Used by
    `Lesson.clean()` to validate and by `Lesson.get_video_embed()` to
    pick a renderer.
    """
    if not url:
        return None
    try:
        parsed = urlparse(url)
    except Exception:
        return None
    host = (parsed.hostname or "").lower()

    # YouTube — accept watch?v=, youtu.be/<id>, /embed/<id>, /shorts/<id>.
    if host in _YOUTUBE_HOSTS:
        vid = None
        if host.endswith("youtu.be"):
            vid = parsed.path.lstrip("/").split("/", 1)[0] or None
        elif parsed.path == "/watch":
            qs = parse_qs(parsed.query or "")
            vid = (qs.get("v") or [None])[0]
        elif parsed.path.startswith(("/embed/", "/shorts/")):
            vid = parsed.path.split("/", 2)[2].split("/", 1)[0] or None
        if vid:
            return {"kind": "youtube", "id": vid,
                    "embed_url": f"https://www.youtube.com/embed/{vid}"}

    # Vimeo — vimeo.com/<id> or player.vimeo.com/video/<id>.
    if host in _VIMEO_HOSTS:
        path = parsed.path.strip("/")
        if path.startswith("video/"):
            path = path.split("/", 1)[1]
        vid = path.split("/", 1)[0]
        if vid.isdigit():
            return {"kind": "vimeo", "id": vid,
                    "embed_url": f"https://player.vimeo.com/video/{vid}"}

    # Direct video file (https URL ending in .mp4/.webm/.m4v).
    if parsed.scheme in ("http", "https") and _DIRECT_VIDEO_RE.search(parsed.path or ""):
        return {"kind": "direct", "id": None, "embed_url": url}

    return None


def validate_video_url(url: str) -> None:
    """Raise ValidationError unless `url` is a recognised provider link."""
    if not url:
        return
    if parse_video_url(url) is None:
        raise ValidationError(
            _("Video URL must be a YouTube, Vimeo, or direct .mp4/.webm/.m4v link.")
        )


def validate_resource_file(file_obj, resource_type: str):
    """Dispatch validator used by `LessonResource.file`. Maps the
    resource_type enum onto the right allowlist."""
    mapping = {
        "video":     validate_video,
        "audio":     validate_audio,
        "pdf":       validate_document,
        "image":     validate_image,
        "worksheet": validate_worksheet,
    }
    fn = mapping.get(resource_type)
    if fn is None:
        # `link` has no file; tolerate any other type by skipping.
        return
    fn(file_obj)
