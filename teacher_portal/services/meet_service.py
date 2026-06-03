"""Google Meet link generation for live sessions.

Flexible by design: when ``GOOGLE_MEET_ENABLED`` is true *and* the Google API
client + credentials are available, it creates a real Calendar event with a
Meet link. Otherwise — dev boxes, missing keys, the client not installed — it
falls back to a realistic mock link so scheduling never breaks.

The real path is intentionally best-effort: any failure logs and degrades to
the mock so an admin/teacher can always schedule.
"""
from __future__ import annotations

import logging
import uuid

from django.conf import settings

logger = logging.getLogger(__name__)


def _mock_meet_link() -> str:
    """A realistic ``https://meet.google.com/abc-defg-hij`` style link.

    The code is random per call (uuid-derived) so two sessions never collide.
    """
    h = uuid.uuid4().hex
    code = f"{h[:3]}-{h[3:7]}-{h[7:10]}"
    return f"https://meet.google.com/{code}"


def _real_meet_link(*, title: str, start, duration_minutes: int) -> str | None:
    """Create a Calendar event with a Meet link via the Google API.

    Returns the Meet URL, or None if the integration isn't usable (so the
    caller falls back to the mock). Never raises.
    """
    creds_file = getattr(settings, "GOOGLE_MEET_CREDENTIALS_FILE", "")
    if not creds_file:
        return None
    try:
        from datetime import timedelta

        from google.oauth2 import service_account  # type: ignore
        from googleapiclient.discovery import build  # type: ignore

        credentials = service_account.Credentials.from_service_account_file(
            creds_file, scopes=["https://www.googleapis.com/auth/calendar"],
        )
        service = build("calendar", "v3", credentials=credentials, cache_discovery=False)
        end = start + timedelta(minutes=duration_minutes or 60)
        event = {
            "summary": title,
            "start": {"dateTime": start.isoformat()},
            "end": {"dateTime": end.isoformat()},
            "conferenceData": {
                "createRequest": {
                    "requestId": uuid.uuid4().hex,
                    "conferenceSolutionKey": {"type": "hangoutsMeet"},
                }
            },
        }
        created = (
            service.events()
            .insert(
                calendarId=getattr(settings, "GOOGLE_MEET_CALENDAR_ID", "primary"),
                body=event,
                conferenceDataVersion=1,
            )
            .execute()
        )
        link = created.get("hangoutLink") or ""
        return link or None
    except Exception:
        logger.exception("Google Meet API failed; falling back to mock link")
        return None


def generate_meet_link(*, title: str, start, duration_minutes: int = 60) -> str:
    """Return a Meet link for a session — real when configured, else mock."""
    if getattr(settings, "GOOGLE_MEET_ENABLED", False):
        link = _real_meet_link(title=title, start=start, duration_minutes=duration_minutes)
        if link:
            return link
    return _mock_meet_link()
