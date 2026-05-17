from __future__ import annotations

from datetime import timedelta

from django.db.models import Avg, Count
from django.utils import timezone

from platform_admin.services.audit_log_service import log_action


def ai_overview_metrics() -> dict:
    now = timezone.now()
    today = now.date()
    data = {
        "requests_today": 0,
        "openai_usage": 0,
        "local_usage": 0,
        "fallback_rate": 0,
        "average_latency": 0,
        "failed_requests": 0,
        "tts_usage": 0,
        "stt_usage": 0,
        "top_errors": [],
        "cost_estimate": 0,
    }
    try:
        from ai_engine.models import ModelPredictionLog

        qs = ModelPredictionLog.objects.filter(created_at__date=today)
        total = qs.count()
        data["requests_today"] = total
        data["openai_usage"] = qs.filter(provider__icontains="openai").count()
        data["local_usage"] = qs.filter(provider__icontains="local").count()
        data["failed_requests"] = qs.filter(success=False).count()
        data["average_latency"] = int(qs.aggregate(avg=Avg("latency_ms"))["avg"] or 0)
        fallback = qs.filter(fallback_used=True).count()
        data["fallback_rate"] = round(fallback / total * 100, 1) if total else 0
        data["top_errors"] = list(
            qs.filter(success=False)
            .exclude(error_message="")
            .values("error_message")
            .annotate(count=Count("id"))
            .order_by("-count")[:5]
        )
        data["cost_estimate"] = round(data["openai_usage"] * 0.002, 2)
    except Exception:
        pass
    try:
        from speech.models import SpeakingAttempt
        data["stt_usage"] = SpeakingAttempt.objects.filter(created_at__date=today).count()
    except Exception:
        pass
    return data


def tutor_logs(params=None):
    params = params or {}
    try:
        from tutor.models import TutorMessage
    except Exception:
        return []
    qs = TutorMessage.objects.select_related("conversation", "conversation__user").order_by("-created_at")
    q = (params.get("q") or "").strip()
    if q:
        qs = qs.filter(content__icontains=q)
    role = (params.get("role") or "").strip()
    if role:
        qs = qs.filter(role=role)
    return qs[:100]


def dataset_review_context():
    ctx = {"examples": [], "builds": [], "reports": []}
    try:
        from ai_training.models import AITrainingExample, DatasetBuild, DatasetQualityReport
        ctx["examples"] = AITrainingExample.objects.order_by("-created_at")[:100]
        ctx["builds"] = DatasetBuild.objects.order_by("-started_at")[:20]
        ctx["reports"] = DatasetQualityReport.objects.select_related("build")[:20]
    except Exception:
        pass
    return ctx


def model_metrics_context():
    ctx = {"evaluations": [], "predictions": []}
    try:
        from ai_training.models import EvaluationRun
        ctx["evaluations"] = EvaluationRun.objects.select_related("build").order_by("-started_at")[:50]
    except Exception:
        pass
    try:
        from ai_engine.models import ModelPredictionLog
        ctx["predictions"] = ModelPredictionLog.objects.order_by("-created_at")[:50]
    except Exception:
        pass
    return ctx


def approve_training_example(request, example):
    example.is_approved = True
    example.save(update_fields=["is_approved"])
    log_action(
        request,
        action_type="ai.training_example.approve",
        object_type=example.__class__.__name__,
        object_id=example.pk,
        description=f"Approved training example #{example.pk}",
    )


def reject_training_example(request, example):
    example.is_approved = False
    example.save(update_fields=["is_approved"])
    log_action(
        request,
        action_type="ai.training_example.reject",
        object_type=example.__class__.__name__,
        object_id=example.pk,
        description=f"Rejected training example #{example.pk}",
    )


def readiness_report() -> dict:
    try:
        from ai_training.models import EvaluationRun
        last_90 = timezone.now() - timedelta(days=90)
        qs = EvaluationRun.objects.filter(started_at__gte=last_90)
        total = qs.count()
        passed = qs.filter(accuracy__gte=0.8).count()
        return {"total": total, "passed": passed, "readiness": round(passed / total * 100, 1) if total else 0}
    except Exception:
        return {"total": 0, "passed": 0, "readiness": 0}
