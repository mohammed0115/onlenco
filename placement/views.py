from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST
from django.views.decorators.http import require_http_methods

from .models import PlacementResult
from .services import assess
from .services.diagnostic_engine import build_diagnostic_profile


# MCQ choices kept here so the view stays the single source of truth
Q1_CHOICES = ["go", "goes", "going", "went"]
Q2_CHOICES = [
    "If I would have known, I will help.",
    "If I had known, I would have helped.",
    "If I knowed, I would helped.",
    "If I know, I would helped.",
]


@login_required
@require_http_methods(["GET", "POST"])
def placement(request):
    """Renders the placement test, runs the AI assessor on submit, and
    persists both the detailed `PlacementResult` and the summary fields
    on the user's `Profile`."""

    profile = request.user.profile
    result_for_template = None

    if request.method == "POST":
        answers = {
            "q1": (request.POST.get("q1") or "").strip(),
            "q2": (request.POST.get("q2") or "").strip(),
            "q3": (request.POST.get("q3") or "").strip(),
            "q4": (request.POST.get("q4") or "").strip(),
            "q5": (request.POST.get("q5_transcript") or "").strip(),
        }

        if (
            not answers["q1"]
            or not answers["q2"]
            or len(answers["q3"]) < 10
            or len(answers["q4"]) < 20
            or len(answers["q5"]) < 30
        ):
            if len(answers["q5"]) < 30:
                messages.error(request, "Please record a longer spoken answer (at least 5 sentences).")
            else:
                messages.error(request, "Please answer all questions.")
            return render(request, "placement/placement.html", {
                "profile": profile,
                "result": None,
                "q1_choices": Q1_CHOICES,
                "q2_choices": Q2_CHOICES,
                "retaking": bool(request.session.get("placement_retake")),
            })

        result = assess(answers)

        PlacementResult.objects.create(
            user=request.user,
            level=result["level"],
            written_score=result.get("written_score"),
            speaking_score=result.get("speaking_score"),
            feedback=result.get("feedback", ""),
            transcript=answers,
        )

        profile.cefr_level = result["level"]
        profile.placement_completed = True
        profile.save(update_fields=["cefr_level", "placement_completed"])

        # Build adaptive diagnostic profile (best-effort).
        try:
            build_diagnostic_profile(request.user, answers, assessment=result)
        except Exception:
            import logging
            logging.getLogger(__name__).exception("Diagnostic engine failed")

        request.session.pop("placement_retake", None)

        result_for_template = {
            "level": result["level"],
            "feedback": result.get("feedback", ""),
        }

        return render(request, "placement/placement.html", {
            "profile": profile,
            "result": result_for_template,
            "q1_choices": Q1_CHOICES,
            "q2_choices": Q2_CHOICES,
        })

    # GET
    if not profile.placement_completed or request.session.get("placement_retake"):
        return render(request, "placement/placement.html", {
            "profile": profile,
            "result": None,
            "q1_choices": Q1_CHOICES,
            "q2_choices": Q2_CHOICES,
            "retaking": bool(request.session.get("placement_retake")),
        })

    latest = (
        PlacementResult.objects.filter(user=request.user)
        .order_by("-created_at")
        .first()
    )
    history = (
        PlacementResult.objects.filter(user=request.user)
        .order_by("-created_at")[:10]
    )
    return render(request, "placement/already_taken.html", {
        "profile": profile,
        "latest": latest,
        "history": history,
    })


@login_required
@require_POST
def start_retake(request):
    request.session["placement_retake"] = True
    return redirect("placement")
