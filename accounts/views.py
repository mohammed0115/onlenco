from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.core.cache import cache
from django.shortcuts import redirect, render
from django.utils import translation
from django.views.decorators.http import require_http_methods, require_POST

from .forms import SignUpForm, EmailLoginForm
from . import onboarding as onboarding_lib


# Backstop against automated signup floods; tunable via settings/env.
# Kept loose-ish because Sudanese users frequently share one public IP
# behind carrier-grade NAT — a too-low cap would block a classroom or
# household signing up together. 10/hr/IP is the floor we'll allow:
# tight enough to throttle a single-IP bot, loose enough to survive a
# real signup burst from a shared NAT. Rotating-IP botnets are out of
# scope for this limit and must be handled by hCaptcha (already wired).
SIGNUP_RATE_LIMIT_PER_IP_PER_HOUR = getattr(
    settings, "SIGNUP_RATE_LIMIT_PER_IP_PER_HOUR", 10
)


def _client_ip(request) -> str:
    """First IP from X-Forwarded-For (Caddy passes it), else REMOTE_ADDR.
    Strip any :port that proxies sometimes include — same gotcha that
    bit us on the audit-log inet column (commit 1642539)."""
    fwd = request.META.get("HTTP_X_FORWARDED_FOR", "")
    raw = (fwd.split(",", 1)[0].strip() if fwd else request.META.get("REMOTE_ADDR", "")) or "0.0.0.0"
    if raw.startswith("[") and "]" in raw:
        return raw[1:raw.index("]")]
    if raw.count(":") == 1:
        return raw.split(":", 1)[0]
    return raw


def _registration_suspicious_flags(request, user, user_agent: str, ip: str) -> list:
    """Best-effort anti-bot signals recorded on the new student's profile.

    These do NOT block (honeypot/rate-limit do); they let an admin spot
    likely bots in the approval queue. Never raises."""
    flags = []
    try:
        ua = (user_agent or "").lower()
        if not ua or len(ua) < 12 or any(
            tok in ua for tok in ("bot", "crawl", "spider", "python-requests",
                                  "curl", "wget", "httpclient", "scrapy")):
            flags.append("suspicious_user_agent")
        domain = (getattr(user, "email", "") or "").rsplit("@", 1)[-1].lower()
        disposable = set(getattr(settings, "ONLENCO_DISPOSABLE_EMAIL_DOMAINS", []))
        if domain and domain in disposable:
            flags.append("disposable_email")
        # Repeated IP: several registrations from the same IP recently.
        from datetime import timedelta
        from django.utils import timezone
        from accounts.models import StudentApprovalEvent
        if ip and ip != "0.0.0.0":
            recent = StudentApprovalEvent.objects.filter(
                action="registered", ip_address=ip,
                created_at__gte=timezone.now() - timedelta(hours=24),
            ).exclude(user=user).count()
            if recent >= 3:
                flags.append("repeated_ip")
    except Exception:
        import logging
        logging.getLogger(__name__).warning("suspicious-flag calc failed", exc_info=True)
    return flags


def _signup_rate_exceeded(request) -> bool:
    """Returns True if this IP has hit its hourly signup cap."""
    return _rate_exceeded(
        request,
        bucket="signup_rate",
        limit=SIGNUP_RATE_LIMIT_PER_IP_PER_HOUR,
    )


PASSWORD_RESET_RATE_LIMIT_PER_IP_PER_HOUR = getattr(
    settings, "PASSWORD_RESET_RATE_LIMIT_PER_IP_PER_HOUR", 10
)


def _password_reset_rate_exceeded(request) -> bool:
    """Throttle password-reset POSTs by IP.

    The Django default has no rate limit, which lets an attacker spam
    the system with reset emails for arbitrary addresses (cheap for
    them, expensive for our SMTP + annoying for real users). 10 / hour
    / IP is plenty for legitimate use.
    """
    return _rate_exceeded(
        request,
        bucket="pwreset_rate",
        limit=PASSWORD_RESET_RATE_LIMIT_PER_IP_PER_HOUR,
    )


def _rate_exceeded(request, *, bucket: str, limit: int) -> bool:
    """Per-IP per-hour counter. Returns True when the IP is over the limit."""
    ip = _client_ip(request)
    key = f"{bucket}:{ip}"
    n = cache.get(key, 0)
    if n >= limit:
        return True
    # Set with a 1-hour TTL on first hit; subsequent hits just inc.
    if n == 0:
        cache.set(key, 1, 3600)
    else:
        try:
            cache.incr(key)
        except ValueError:
            cache.set(key, 1, 3600)
    return False


def _hcaptcha_verify(request) -> bool:
    """Verify the hCaptcha token when hCaptcha is fully configured.

    hCaptcha is "on" only when BOTH keys are present: the site key
    renders the widget, the secret verifies the token. If either is
    missing the widget can't produce a token, so demanding one would
    reject every signup — a missing key therefore means "disabled".
    Returns True when verified OR when hCaptcha is not (fully) enabled.
    """
    site_key = (getattr(settings, "HCAPTCHA_SITE_KEY", "") or "").strip()
    secret = (getattr(settings, "HCAPTCHA_SECRET", "") or "").strip()
    if not (site_key and secret):
        return True   # feature disabled or misconfigured — never block signups
    token = (request.POST.get("h-captcha-response") or "").strip()
    if not token:
        return False
    try:
        import requests
        r = requests.post(
            "https://hcaptcha.com/siteverify",
            data={"secret": secret, "response": token, "remoteip": _client_ip(request)},
            timeout=8,
        )
        return bool((r.json() or {}).get("success"))
    except Exception:
        import logging
        logging.getLogger(__name__).warning("hCaptcha verification failed", exc_info=True)
        return False


def _safe_next(request):
    """A same-origin ``?next=`` destination, or None. Guards open-redirects."""
    if request is None:
        return None
    from django.utils.http import url_has_allowed_host_and_scheme
    nxt = (request.POST.get("next") or request.GET.get("next") or "").strip()
    if nxt and url_has_allowed_host_and_scheme(
        nxt, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return nxt
    return None


def _post_login_destination(user, request=None):
    # Onboarding/placement gating always wins — a ``next`` link must not let a
    # user skip required onboarding.
    nxt = onboarding_lib.next_url_for(user)
    if nxt:
        return nxt
    # Otherwise honour an explicit, same-origin ``?next=`` (deep-linking).
    safe = _safe_next(request)
    if safe:
        return safe
    try:
        from teacher_portal.services.role_service import RoleService
        return RoleService.get_default_landing_page(user)
    except Exception:
        return "dashboard"


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


def _dispatch_signup_emails(user) -> None:
    """Send the verification OTP + signup notifications in a background
    thread so slow SMTP delivery never blocks the signup response.

    Inline delivery used to freeze the signup request for 30s+ (and
    could hang indefinitely on an unreachable mail host), so users gave
    up before the page returned. This is best-effort: any failure is
    logged and swallowed — the account already exists and the user can
    request a fresh code from the verify-email page.
    """
    import logging
    import threading

    user_pk = user.pk

    def _work():
        from django.contrib.auth import get_user_model
        from django.db import connections
        log = logging.getLogger(__name__)
        try:
            u = get_user_model().objects.filter(pk=user_pk).first()
            if u is None:
                return
            try:
                from notifications.services import issue_verification_token
                issue_verification_token(u)
            except Exception:
                log.exception("signup emails: issue verification token failed")
            try:
                from notifications import constants as C
                from notifications.services import NotificationService
                notifier = NotificationService()
                notifier.trigger(
                    C.USER_REGISTERED,
                    user=u,
                    payload={"cta_url": "/placement/", "cta_label": "Start placement test"},
                )
                notifier.notify_admins(
                    C.NEW_STUDENT_REGISTERED,
                    payload={
                        "username": u.username,
                        "email": u.email,
                        "joined_at": u.date_joined.isoformat() if getattr(u, "date_joined", None) else "",
                        "cta_url": "/admin/auth/user/",
                    },
                )
            except Exception:
                log.exception("signup emails: notifications failed")
        finally:
            # Release this thread's DB connection — it is not managed
            # by the request/response cycle.
            connections.close_all()

    threading.Thread(
        target=_work, name=f"signup-emails-{user_pk}", daemon=True
    ).start()


@require_http_methods(["GET", "POST"])
def auth_view(request):
    """Combined sign-in / sign-up page. The mode is controlled by either
    the `mode` querystring (?mode=signup) or the form's hidden `mode` field."""

    if request.user.is_authenticated:
        return redirect(_post_login_destination(request.user, request))

    mode = request.POST.get("mode") or request.GET.get("mode") or "signin"
    if mode not in ("signin", "signup"):
        mode = "signin"

    signin_form = EmailLoginForm(request)
    signup_form = SignUpForm()

    if request.method == "POST":
        if mode == "signup":
            # Rate-limit by IP first — cheapest check, blocks brute-force
            # signup floods before we even validate the form.
            if _signup_rate_exceeded(request):
                messages.error(
                    request,
                    "Too many signup attempts from your network. Please try again later.",
                )
                return render(request, "accounts/auth.html", {
                    "mode": "signup",
                    "signin_form": signin_form,
                    "signup_form": signup_form,
                    "HCAPTCHA_SITE_KEY": getattr(settings, "HCAPTCHA_SITE_KEY", "") or "",
                })
            signup_form = SignUpForm(request.POST)
            if not signup_form.is_valid():
                # Field errors render inline next to each input; this
                # toast is the at-a-glance signal so an invalid signup
                # is never a silent no-op the user can't diagnose.
                messages.error(
                    request,
                    "We couldn't create your account. Please review the form and try again.",
                )
            elif not _hcaptcha_verify(request):
                messages.error(request, "Please complete the CAPTCHA challenge and try again.")
            else:
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

                # Record the registration into the approval gate (sets the
                # student to pending + captures IP/UA + anti-bot signals).
                try:
                    from accounts import approval as _approval
                    ua = request.META.get("HTTP_USER_AGENT", "")
                    ip = _client_ip(request)
                    flags = _registration_suspicious_flags(request, user, ua, ip)
                    _approval.record_registration(
                        user, ip=ip, user_agent=ua,
                        suspicious_flags=flags, suspicious_score=len(flags),
                    )
                except Exception:
                    import logging
                    logging.getLogger(__name__).exception("approval record_registration failed")

                # Issue the OTP + fire signup notifications OFF-THREAD.
                # SMTP delivery is slow and can hang on an unreachable
                # mail host; sending it inline used to freeze the signup
                # request so users abandoned it before it completed.
                _dispatch_signup_emails(user)

                # Authenticate properly so the session is bound.
                auth_user = authenticate(
                    request,
                    username=signup_form.cleaned_data["email"],
                    password=signup_form.cleaned_data["password"],
                )
                if auth_user is not None:
                    login(request, auth_user)
                    messages.success(
                        request,
                        "Account created. We sent a 6-digit code to your email.",
                    )
                    return redirect("verify_email_otp")
                # Account was created but auto-login failed — never leave
                # the user on a silent page; send them to sign in.
                messages.success(
                    request,
                    "Your account was created. Please sign in to continue.",
                )
                return redirect("auth")
        else:
            signin_form = EmailLoginForm(request, data=request.POST)
            if signin_form.is_valid():
                login(request, signin_form.get_user())
                return redirect(_post_login_destination(signin_form.get_user(), request))
            else:
                messages.error(request, "Invalid email or password.")

    return render(request, "accounts/auth.html", {
        "mode": mode,
        "signin_form": signin_form,
        "signup_form": signup_form,
        "HCAPTCHA_SITE_KEY": getattr(settings, "HCAPTCHA_SITE_KEY", "") or "",
    })


@login_required
@require_POST
def logout_view(request):
    # POST-only: GET-logout is a CSRF vector — a hostile site embedding
    # <img src="/auth/logout/"> would silently sign the user out. Every
    # logout button in our templates already uses <form method="post">.
    logout(request)
    return redirect("home")


@login_required
@require_http_methods(["GET"])
def pending_approval(request):
    """Waiting page for students who are not yet approved.

    Approved students (or staff/teachers) are bounced to their dashboard.
    Shows email-verification status, support contact, and a logout button —
    NO dashboard links and NO internal anti-bot detail.
    """
    profile = getattr(request.user, "profile", None)
    if profile is None or profile.is_approved_student:
        return redirect(_post_login_destination(request.user, request))
    return render(request, "accounts/pending_approval.html", {
        "approval_status": profile.approval_status,
        "email_verified": profile.email_verified,
        "support_email": getattr(settings, "SUPPORT_EMAIL", "support@onlenco.academy"),
        "lang": _request_language(request),
    })


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
                # Advance the approval gate: pending_email_verification →
                # pending_admin_approval (writes an audit event).
                try:
                    from accounts import approval as _approval
                    _approval.mark_email_verified(request.user)
                except Exception:
                    import logging
                    logging.getLogger(__name__).exception("mark_email_verified failed")
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

    # Pull the new subscription-system snapshots so the profile page can
    # show plan + AI Tutor quota + voice preference at a glance.
    plan = None
    quota_snapshot = None
    voice_preview = None
    try:
        from subscriptions.services import preference_service, quota_service, subscription_service
        plan = subscription_service.active_plan_for(request.user)
        quota_snapshot = quota_service.quota_snapshot(request.user)
        voice_preview = preference_service.preference_snapshot(request.user)
    except Exception:
        import logging
        logging.getLogger(__name__).exception("profile_view: subscriptions snapshot failed")

    return render(request, "accounts/profile.html", {
        "profile": profile,
        "user": request.user,
        "active_plan": plan,
        "quota_snapshot": quota_snapshot,
        "voice_preview": voice_preview,
    })


@login_required
@require_http_methods(["GET", "POST"])
def change_password(request):
    """Self-service password change. Required for accounts flagged with
    ``must_change_password`` (admin-issued temporary password)."""
    profile = getattr(request.user, "profile", None)
    forced = bool(getattr(profile, "must_change_password", False))

    if request.method == "POST":
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            form.save()
            update_session_auth_hash(request, form.user)
            if profile is not None and profile.must_change_password:
                profile.must_change_password = False
                profile.save(update_fields=["must_change_password"])
            messages.success(request, "Password updated successfully.")
            try:
                from teacher_portal.services.role_service import RoleService
                return redirect(RoleService.get_default_landing_page(request.user))
            except Exception:
                return redirect("profile")
    else:
        form = PasswordChangeForm(request.user)
    return render(request, "accounts/change_password.html", {"form": form, "forced": forced})


# ---------------------------------------------------------------------------
# Throttled password-reset view
# ---------------------------------------------------------------------------

from django.contrib.auth import views as auth_views  # noqa: E402 — late import


class ThrottledPasswordResetView(auth_views.PasswordResetView):
    """Django's PasswordResetView with a per-IP hourly throttle.

    The plain view will happily send reset emails for any address the
    attacker provides — that's a cheap spam vector (and a tiny user-
    enumeration nuisance via timing). ``_password_reset_rate_exceeded``
    caps how many POSTs one IP can fire per hour; over the limit, we
    show a friendly message and bounce back to the form instead of
    quietly mailing.
    """

    def post(self, request, *args, **kwargs):
        if _password_reset_rate_exceeded(request):
            messages.warning(
                request,
                "Too many password-reset attempts from your network. "
                "Please try again in an hour.",
            )
            return redirect("password_reset")
        return super().post(request, *args, **kwargs)
