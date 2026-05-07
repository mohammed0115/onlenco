from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from .forms import PaymentSubmissionForm
from .models import PLAN_DETAILS, PaymentMethodAccount


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
def payment_history(request):
    latest = request.user.payment_submissions.order_by("-created_at").first()
    last_rejected = latest if (latest and latest.status == "rejected") else None

    return render(request, "payments/history.html", {
        "submissions": request.user.payment_submissions.all(),
        "profile": request.user.profile,
        "last_rejected": last_rejected,
    })

