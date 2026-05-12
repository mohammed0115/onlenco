"""Daily-learning HTML views.

These are thin: the heavy logic lives in services. The templates are
bilingual (Arabic / English) and rely on the project's existing RTL
setup (LanguagePreferenceMiddleware + base.html `dir` attr).
"""
from __future__ import annotations

import logging

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import DailyGoal, DailyLearningItem, DailyLearningPlan
from .services import daily_plan_generator, daily_progress_service

logger = logging.getLogger(__name__)


@login_required
def daily_plan_view(request):
    """Today's plan landing page."""
    on_date = timezone.localdate()
    plan = DailyLearningPlan.objects.filter(
        user=request.user, date=on_date,
    ).prefetch_related("items").first()
    if not plan:
        # First visit of the day — create the plan transparently.
        try:
            plan = daily_plan_generator.generate_for_user(request.user, on_date=on_date)
        except Exception:
            logger.exception("daily plan auto-generate failed")
            plan = None

    goals = DailyGoal.objects.filter(user=request.user, date=on_date)
    streak = _safe_streak(request.user, on_date)
    context = {
        "plan": plan,
        "items": list(plan.items.all()) if plan else [],
        "goals": list(goals),
        "streak": streak,
        "motivation_message": (plan.metadata.get("motivation_message") if plan else ""),
        "progress_percent": plan.progress_percent if plan else 0,
    }
    return render(request, "daily_learning/daily_plan.html", context)


@login_required
def daily_review_view(request):
    """Review-mistakes page — just the review_mistake items of today's plan."""
    on_date = timezone.localdate()
    plan = DailyLearningPlan.objects.filter(user=request.user, date=on_date).first()
    review_items = []
    if plan:
        review_items = list(plan.items.filter(item_type="review_mistake"))
    return render(request, "daily_learning/daily_review.html", {
        "plan": plan,
        "items": review_items,
    })


@login_required
def daily_challenge_view(request):
    """Challenge-of-the-day page — shows the day's DailyGoal targets."""
    on_date = timezone.localdate()
    goals = list(DailyGoal.objects.filter(user=request.user, date=on_date))
    plan = DailyLearningPlan.objects.filter(user=request.user, date=on_date).first()
    return render(request, "daily_learning/daily_challenge.html", {
        "plan": plan,
        "goals": goals,
    })


@require_POST
@login_required
def complete_item(request, item_id: int):
    """POST endpoint to mark a single item complete from the HTML page."""
    item = get_object_or_404(
        DailyLearningItem.objects.select_related("daily_plan"),
        id=item_id,
        daily_plan__user=request.user,
    )
    answer = (request.POST.get("answer") or "").strip()
    daily_progress_service.mark_item_complete(item, user_answer=answer)
    return JsonResponse({"ok": True, "item_id": item.id, "is_completed": True})


@require_POST
@login_required
def complete_plan(request):
    """POST endpoint to finalize the plan and write the result."""
    on_date = timezone.localdate()
    plan = DailyLearningPlan.objects.filter(user=request.user, date=on_date).first()
    if not plan:
        return HttpResponseBadRequest("No plan to complete.")
    force = (request.POST.get("force") == "1")
    result = daily_progress_service.complete_plan(plan, force=force)
    return JsonResponse({
        "ok": True,
        "plan_id": plan.id,
        "status": plan.status,
        "score": result.score if result else 0,
        "xp_earned": result.xp_earned if result else 0,
    })


# --- helpers --------------------------------------------------------

def _safe_streak(user, on_date) -> int:
    try:
        from motivation.services import streak_service
        return streak_service.get_current_streak(user, on_date)
    except Exception:
        return 0
