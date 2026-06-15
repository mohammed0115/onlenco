"""Secure audio delivery helper (Phase 19.0G).

Builds an HTTP response that streams an uploaded chapter recording from
storage **without** exposing the raw ``MEDIA_URL`` / absolute filesystem
path. Callers are responsible for authorization (subscription, publish /
copyright gate, an active ``LibraryAudioSession``, or staff permission)
*before* calling these helpers.
"""
from __future__ import annotations

import mimetypes
import os

from django.http import FileResponse

# Only the formats the Platform Admin upload form accepts.
AUDIO_CONTENT_TYPES = {
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".m4a": "audio/mp4",
}


def _content_type_for(name: str) -> str:
    ext = os.path.splitext(name or "")[1].lower()
    return (
        AUDIO_CONTENT_TYPES.get(ext)
        or mimetypes.guess_type(name or "")[0]
        or "application/octet-stream"
    )


def audio_file_response(field_file, *, download: bool = False) -> FileResponse:
    """Stream a FieldFile as a private, inline audio response.

    The file handle comes from the storage backend (``field_file.open``),
    so no absolute path is leaked. Range requests are not implemented yet
    (documented as a later enhancement); the full file is returned.
    """
    name = field_file.name or ""
    fh = field_file.open("rb")
    resp = FileResponse(fh, content_type=_content_type_for(name))
    disposition = "attachment" if download else "inline"
    # Only the basename — never the storage path / absolute filesystem path.
    resp["Content-Disposition"] = f'{disposition}; filename="{os.path.basename(name)}"'
    # Protected media: do not let shared caches / proxies retain it.
    resp["Cache-Control"] = "private, no-store"
    # Tell nginx not to buffer when proxying a streamed response.
    resp["X-Accel-Buffering"] = "no"
    return resp
