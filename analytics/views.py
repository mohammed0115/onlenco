from django.shortcuts import render

from .decorators import admin_required
from .services import compute_metrics
from .services_learning import compute_learning_metrics


@admin_required
def analytics_dashboard(request):
    metrics = compute_metrics()
    return render(request, "analytics/dashboard.html", {"metrics": metrics})


@admin_required
def learning_analytics_dashboard(request):
    days_raw = request.GET.get("days") or "30"
    try:
        days = max(1, min(365, int(days_raw)))
    except ValueError:
        days = 30
    cefr_level = (request.GET.get("cefr") or "").strip() or None
    skill_id_raw = request.GET.get("skill")
    skill_id = None
    if skill_id_raw:
        try:
            skill_id = int(skill_id_raw)
        except ValueError:
            skill_id = None

    metrics = compute_learning_metrics(days=days, cefr_level=cefr_level, skill_id=skill_id)
    return render(
        request,
        "analytics/learning_dashboard.html",
        {"metrics": metrics, "filters": {"days": days, "cefr": cefr_level, "skill": skill_id}},
    )
