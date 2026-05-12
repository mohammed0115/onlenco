from django.contrib import messages
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import translation
from django.views.decorators.http import require_http_methods, require_POST

from .forms import SignUpForm, EmailLoginForm
from . import onboarding as onboarding_lib


def _request_language(request) -> str:
    """Best-effort read of the active locale: ``ar`` or ``en``."""
    candidates = [
        getattr(request, "LANGUAGE_CODE", None),
        translation.get_language(),
    ]
    for c in candidates:
        if not c:
            continue
        c = c.lower()
        if c.startswith("ar"):
            return "ar"
        if c.startswith("en"):
            return "en"
    return "ar"


@require_http_methods(["GET", "POST"])
def auth_view(request):
    """Combined sign-in / sign-up page. The mode is controlled by either
    the `mode` querystring (?mode=signup) or the form's hidden `mode` field."""

    if request.user.is_authenticated:
        nxt = onboarding_lib.next_url_for(request.user)
        return redirect(nxt or "dashboard")

    mode = request.POST.get("mode") or request.GET.get("mode") or "signin"
    if mode not in ("signin", "signup"):
        mode = "signin"

    signin_form = EmailLoginForm(request)
    signup_form = SignUpForm()

    if request.method == "POST":
        if mode == "signup":
            signup_form = SignUpForm(request.POST)
            if signup_form.is_valid():
                user = signup_form.save()

                # Persist the active request language onto the profile +
                # notification preference BEFORE notifications fire, so
                # the welcome / verification emails are rendered in the
                # right language from message #1.
                lang = _request_language(request)
                try:
                    if hasattr(user, "profile") and user.profile.preferred_language != lang:
                        user.profile.preferred_language = lang
                        user.profile.save(update_fields=["preferred_language"])
                    from notifications.models import NotificationPreference
                    pref, _ = NotificationPreference.objects.get_or_create(user=user)
                    if pref.language != lang:
                        pref.language = lang
                        pref.save(update_fields=["language"])
                except Exception:
                    import logging
                    logging.getLogger(__name__).exception("set signup language failed")

                # Notifications (best-effort, never blocks)
                try:
                    from notifications import constants as C
                    from notifications.services import NotificationService
                    notifier = NotificationService()
                    notifier.trigger(
                        C.USER_REGISTERED,
                        user=user,
                        payload={"cta_url": "/placement/", "cta_label": "Start placement test"},
                    )
                    notifier.notify_admins(
                        C.NEW_STUDENT_REGISTERED,
                        payload={
                            "username": user.username,
                            "email": user.email,
                            "joined_at": user.date_joined.isoformat() if getattr(user, "date_joined", None) else "",
                            "cta_url": "/admin/auth/user/",
                        },
                    )
                except Exception:
                    import logging
                    logging.getLogger(__name__).exception("notify on signup view failed")
                # Authenticate properly so the session is bound
                user = authenticate(
                    request,
                    username=signup_form.cleaned_data["email"],
                    password=signup_form.cleaned_data["password"],
                )
                if user is not None:
                    login(request, user)
                    messages.success(
                        request,
                        "Account created. We sent a 6-digit code to your email.",
                    )
                    return redirect("verify_email_otp")
        else:
            signin_form = EmailLoginForm(request, data=request.POST)
            if signin_form.is_valid():
                login(request, signin_form.get_user())
                nxt = onboarding_lib.next_url_for(signin_form.get_user())
                return redirect(nxt or "dashboard")
            else:
                messages.error(request, "Invalid email or password.")

    return render(request, "accounts/auth.html", {
        "mode": mode,
        "signin_form": signin_form,
        "signup_form": signup_form,
    })


@login_required
@require_http_methods(["GET", "POST"])
def logout_view(request):
    logout(request)
    return redirect("home")


@require_http_methods(["GET"])
def verify_email(request, token: str):
    """Consume an email-verification URL token (link from the email)."""
    from notifications.services import consume_verification_token

    ok = consume_verification_token(token)
    if ok:
        messages.success(request, "Your email is verified. Welcome!")
    else:
        messages.error(request, "This verification link is invalid or expired.")
    return redirect("auth")


@require_http_methods(["GET", "POST"])
def verify_email_otp(request):
    """Page where the student types the 6-digit code from the verification email.

    Expects to be reached after registration (the user is logged in but
    `profile.email_verified` is still False). Reachable as
    `/auth/verify-email/[?code=NNNNNN]`.
    """
    from .forms import EmailOTPForm
    from notifications.services import (
        consume_verification_token,
        issue_verification_token,
    )

    if not request.user.is_authenticated:
        messages.warning(request, "Sign in to verify your email.")
        return redirect("auth")

    profile = request.user.profile
    if profile.email_verified:
        messages.info(request, "Your email is already verified.")
        return redirect("dashboard")

    initial = {"code": request.GET.get("code", "")}
    if request.method == "POST":
        form = EmailOTPForm(request.POST)
        if form.is_valid():
            ok = consume_verification_token(form.cleaned_data["code"], user=request.user)
            if ok:
                messages.success(request, "Your email is verified. Welcome!")
                nxt = onboarding_lib.next_url_for(request.user)
                return redirect(nxt or "dashboard")
            messages.error(
                request,
                "That code is invalid or expired. Check your inbox or request a new one.",
            )
    elif initial["code"]:
        # ?code=… came in via the email's CTA link → try once automatically.
        if consume_verification_token(initial["code"], user=request.user):
            messages.success(request, "Your email is verified. Welcome!")
            return redirect("dashboard")
        form = EmailOTPForm(initial=initial)
    else:
        form = EmailOTPForm()

    if request.method == "POST" and request.POST.get("resend"):
        issue_verification_token(request.user)
        messages.info(request, "We've sent you a new code.")
        form = EmailOTPForm()

    return render(request, "accounts/verify_email_otp.html", {
        "form": form,
        "email": request.user.email,
    })


@login_required
@require_http_methods(["POST"])
def resend_email_otp(request):
    """Re-issue a fresh OTP and send it. POST only (to require CSRF)."""
    from notifications.services import issue_verification_token

    issue_verification_token(request.user)
    messages.info(request, "A fresh verification code is on its way.")
    return redirect("verify_email_otp")


# ---------------------------------------------------------------------------
# Onboarding choice
# ---------------------------------------------------------------------------

@login_required
@require_http_methods(["GET"])
def onboarding_choice(request):
    """The "How would you like to start?" page.

    Bypasses to dashboard for users who have already completed
    onboarding (so the page can't be reached twice unless an admin
    flips the flag back)."""
    profile = request.user.profile
    if not onboarding_lib.needs_onboarding(profile):
        return redirect("dashboard")
    return render(request, "accounts/onboarding_choice.html", {
        "profile": profile,
        "preferred_language": profile.preferred_language or "ar",
    })


@login_required
@require_POST
def onboarding_beginner(request):
    """Action for the "Start From Beginner" card.

    Sets the user's level to A0, seeds a `StudentLearningProfile`, marks
    onboarding complete with `path='beginner_start'`, and redirects to
    the dashboard. Idempotent — re-clicking is safe."""
    onboarding_lib.complete_beginner_onboarding(request.user)
    messages.success(
        request,
        "We'll start you with simple lessons. You can take a placement test later anytime.",
    )
    return redirect("dashboard")


@login_required
@require_POST
def onboarding_placement(request):
    """Action for the "Take Placement Test" card.

    Routes into the new dynamic-bank flow which creates a
    `PlacementAttempt` and walks the student through Step 1 (5 written
    questions) → Step 2 (5 speaking questions) → result page. The old
    monolithic `/placement/` page is still available as a backward-
    compatible fallback for users mid-flight on the previous design.
    """
    # Stamp the chosen path immediately so abandoned-mid-test users are
    # still recognisable as "started placement, never finished" rather
    # than orphaned with an empty onboarding_path.
    profile = request.user.profile
    if profile.onboarding_path != "placement_test":
        profile.onboarding_path = "placement_test"
        profile.save(update_fields=["onboarding_path"])
    return redirect("placement_start")


# ---------------------------------------------------------------------------
# Profile / settings
# ---------------------------------------------------------------------------

@login_required
@require_http_methods(["GET", "POST"])
def profile_view(request):
    """Self-service profile + settings page.

    GET  — renders profile snapshot + the "Retake placement test" CTA
           (the audit-item-#14 entry point that previously lived only
           on the dashboard).
    POST — saves the `preferred_language` form. Other state-changing
           actions (retake) are delivered through dedicated endpoints
           so this page stays a control panel rather than a multi-form
           kitchen sink.
    """
    profile = request.user.profile

    if request.method == "POST":
        new_lang = (request.POST.get("preferred_language") or "").strip().lower()
        if new_lang in ("en", "ar"):
            profile.preferred_language = new_lang
            profile.save(update_fields=["preferred_language"])
            messages.success(request, "Your preferences were saved.")
        else:
            messages.error(request, "Unsupported language.")
        return redirect("profile")

    return render(request, "accounts/profile.html", {
        "profile": profile,
        "user": request.user,
    })
