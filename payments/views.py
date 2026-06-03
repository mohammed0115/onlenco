from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .forms import PaymentSubmissionForm
from .models import PLAN_DETAILS, PaymentMethodAccount


def _student_cefr_level(user) -> str:
    """Best-effort current CEFR level for a student (profile, else placement)."""
    level = (getattr(getattr(user, "profile", None), "cefr_level", "") or "").strip()
    if level:
        return level
    try:
        from placement.models import PlacementResult
        result = PlacementResult.objects.filter(user=user).order_by("-created_at").first()
        return (result.level if result else "") or ""
    except Exception:
        return ""


def _candidate_teachers(cefr_level: str, limit: int = 3):
    """Up to ``limit`` approved, active teachers matching the level.

    Matching is by ``cefr_focus`` (blank focus = any level). Featured and
    higher-rated teachers come first. Falls back gracefully if fewer match.
    """
    from teacher_portal.models import TeacherProfile
    qs = (
        TeacherProfile.objects
        .filter(is_active=True, approved_at__isnull=False)
        .select_related("user")
        .order_by("-is_featured", "-rating", "user__username")
    )
    matched = [tp for tp in qs if tp.teaches_level(cefr_level)]
    return matched[:limit]


@login_required
@require_http_methods(["GET", "POST"])
def subscribe(request):
    """Pick a plan + payment method, view destination account, upload a
    screenshot. Submission lands as `pending` until an admin approves it
    from /admin/."""

    profile = request.user.profile

    accounts_qs = PaymentMethodAccount.objects.filter(is_active=True)
    accounts = {
        a.method: {
            "label": a.label,
            "account": a.account_number,
            "name": a.account_holder,
            "instructions": a.instructions,
        }
        for a in accounts_qs
    }

    prefill_plan = (request.GET.get("plan") or "").strip()
    prefill_method = (request.GET.get("method") or "").strip()

    latest = request.user.payment_submissions.order_by("-created_at").first()
    last_rejected = latest if (latest and latest.status == "rejected") else None

    if request.method == "POST":
        form = PaymentSubmissionForm(request.POST, request.FILES)
        if form.is_valid():
            submission = form.save(user=request.user)
            profile.subscription_status = "pending"
            profile.save(update_fields=["subscription_status"])
            messages.success(
                request,
                "Payment submitted! We'll verify it within 24 hours.",
            )
            try:
                from notifications import constants as C
                from notifications.services import NotificationService
                notifier = NotificationService()
                notifier.trigger(
                    C.PAYMENT_SUBMITTED,
                    user=request.user,
                    payload={
                        "plan": submission.plan,
                        "amount_sdg": submission.amount_sdg,
                        "cta_url": "/payments/history/",
                        "cta_label": "View status",
                        "dedup_key": f"submit:{submission.id}",
                    },
                )
                notifier.notify_admins(
                    C.NEW_PAYMENT_PENDING,
                    payload={
                        "username": request.user.username,
                        "plan": submission.plan,
                        "amount_sdg": submission.amount_sdg,
                        "method": submission.method,
                        "cta_url": f"/admin/payments/paymentsubmission/{submission.id}/change/",
                        "cta_label": "Review",
                    },
                )
            except Exception:
                import logging
                logging.getLogger(__name__).exception("notify on payment submit failed")
            return redirect("payment_history")
    else:
        form = PaymentSubmissionForm()

    return render(request, "payments/subscribe.html", {
        "form": form,
        "accounts": accounts,
        "plans": PLAN_DETAILS,
        "profile": profile,
        "submissions": request.user.payment_submissions.all()[:5],
        "last_rejected": last_rejected,
        "prefill_plan": prefill_plan,
        "prefill_method": prefill_method,
    })


@login_required
@require_http_methods(["GET", "POST"])
def choose_teacher(request):
    """Marketplace teacher picker — additive, never gates lesson access.

    Shows up to three approved teachers matching the student's CEFR level
    and lets them pick one. Posting a ``teacher_id`` sets the single active
    StudentTeacherRelation.
    """
    from teacher_portal.models import StudentTeacherRelation

    cefr_level = _student_cefr_level(request.user)

    if request.method == "POST":
        teacher_id = (request.POST.get("teacher_id") or "").strip()
        User = get_user_model()
        teacher = get_object_or_404(
            User, pk=teacher_id, teacher_profile__is_active=True,
            teacher_profile__approved_at__isnull=False,
        )
        StudentTeacherRelation.set_active(request.user, teacher, cefr_level=cefr_level)
        messages.success(request, "Your teacher has been selected.")
        return redirect("choose_teacher")

    current = StudentTeacherRelation.active_for(request.user)
    return render(request, "payments/choose_teacher.html", {
        "candidates": _candidate_teachers(cefr_level),
        "current_teacher": current.teacher if current else None,
        "cefr_level": cefr_level,
        "profile": request.user.profile,
    })


@login_required
def payment_history(request):
    latest = request.user.payment_submissions.order_by("-created_at").first()
    last_rejected = latest if (latest and latest.status == "rejected") else None

    return render(request, "payments/history.html", {
        "submissions": request.user.payment_submissions.all(),
        "profile": request.user.profile,
        "last_rejected": last_rejected,
    })

