"""Public unsubscribe view (signed-token, no login needed).

The token is `TimestampSigner`-signed and encodes the user_id. Visiting
`/notifications/unsubscribe/<token>/` toggles all opt-out flags off and
shows a small confirmation page.
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from .services.preference_service import PreferenceService

User = get_user_model()
SIGNER_SALT = "notifications.unsubscribe"
TOKEN_MAX_AGE = 60 * 60 * 24 * 30  # 30 days


def make_unsubscribe_token(user) -> str:
    return TimestampSigner(salt=SIGNER_SALT).sign(str(user.id))


@require_http_methods(["GET", "POST"])
def unsubscribe(request, token: str):
    signer = TimestampSigner(salt=SIGNER_SALT)
    try:
        user_id = signer.unsign(token, max_age=TOKEN_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return HttpResponse("Invalid or expired unsubscribe link.", status=400)

    user = User.objects.filter(pk=int(user_id)).first()
    if not user:
        return HttpResponse("User not found.", status=404)

    pref = PreferenceService.get_or_create_for(user)
    if request.method == "POST":
        pref.learning_updates = False
        pref.payment_updates = False
        pref.weekly_summary = False
        pref.marketing_emails = False
        pref.save(update_fields=[
            "learning_updates", "payment_updates",
            "weekly_summary", "marketing_emails",
        ])
        return render(request, "notifications/unsubscribe_done.html", {"user": user})
    return render(request, "notifications/unsubscribe_confirm.html", {"user": user, "token": token})
