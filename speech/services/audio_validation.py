"""Validate browser-uploaded audio before it reaches Whisper.

Two cheap checks:
  - mime/extension allowlist — webm/ogg/mp3/wav/m4a only
  - size cap — 10 MB (≈10 minutes of compressed speech)

Returns either None (valid) or a dict {code, message} the API view turns
into a 400 JSON error. Never raises.
"""
from __future__ import annotations

import os

ALLOWED_EXTS = {".webm", ".ogg", ".oga", ".mp3", ".wav", ".m4a", ".mp4"}
ALLOWED_MIME_PREFIXES = ("audio/", "video/webm", "video/mp4")
MAX_BYTES = 10 * 1024 * 1024


def validate_audio_upload(file_obj) -> dict | None:
    name = (getattr(file_obj, "name", "") or "").lower()
    ext = os.path.splitext(name)[1]
    mime = (getattr(file_obj, "content_type", "") or "").lower()

    if ext and ext not in ALLOWED_EXTS:
        return {"code": "bad_extension",
                "message": f"Audio extension {ext} is not supported."}
    if mime and not mime.startswith(ALLOWED_MIME_PREFIXES):
        return {"code": "bad_mime",
                "message": f"Audio mime {mime} is not supported."}

    size = getattr(file_obj, "size", 0) or 0
    if size > MAX_BYTES:
        mb = size / (1024 * 1024)
        return {"code": "too_large",
                "message": f"Audio is too large ({mb:.1f} MB). Limit is "
                           f"{MAX_BYTES // (1024 * 1024)} MB."}
    if size == 0:
        return {"code": "empty",
                "message": "Audio file is empty."}
    return None
