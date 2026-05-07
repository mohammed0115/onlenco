from django.shortcuts import render

from .decorators import admin_required
from .services import compute_metrics


@admin_required
def analytics_dashboard(request):
    metrics = compute_metrics()
    return render(request, "analytics/dashboard.html", {"metrics": metrics})
