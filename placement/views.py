from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from .models import (
    PlacementAttempt, PlacementAttemptQuestion, PlacementResult,
)
from .services import assess
from .services.diagnostic_engine import build_diagnostic_profile
from .services.dynamic_scoring import score_placement_attempt
from .services.placement_question_selector import create_placement_attempt


# Legacy MCQ choices — kept so the old `/placement/` flow doesn't break
# while the new dynamic /placement/start/ path is rolled out.
Q1_CHOICES = ["go", "goes", "going", "went"]
Q2_CHOICES = [
    "If I would have known, I will help.",
    "If I had known, I would have helped.",
    "If I knowed, I would helped.",
    "If I know, I would helped.",
]


# ---------------------------------------------------------------------------
# Legacy single-page placement (kept for backwards compatibility)
# ---------------------------------------------------------------------------

@login_required
@require_http_methods(["GET", "POST"])
def placement(request):
    """Legacy single-page placement. New users are routed through
    `/placement/start/` → `/placement/<id>/written/` → speaking → result.
    This endpoint stays for users mid-flight on the old design."""

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

        try:
            from accounts.onboarding import complete_placement_onboarding
            complete_placement_onboarding(profile, level=result["level"])
        except Exception:
            import logging
            logging.getLogger(__name__).exception("complete_placement_onboarding failed")

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


# ---------------------------------------------------------------------------
# New dynamic flow — picks 5 written + 5 speaking from the bank, persists
# them on a `PlacementAttempt` so refresh keeps the same questions.
# ---------------------------------------------------------------------------

def _user_attempt(request, attempt_id: int) -> PlacementAttempt:
    """Fetch attempt enforcing ownership."""
    return get_object_or_404(
        PlacementAttempt, pk=attempt_id, user=request.user,
    )


@login_required
@require_http_methods(["GET", "POST"])
def placement_start(request):
    """Create a new attempt and redirect into the written step.

    Accepts GET (so a redirect from `onboarding_placement` lands cleanly
    in the browser) AND POST (when the dashboard CTA is a form). Both
    do the same thing: create one `PlacementAttempt` for the user and
    forward them to Step 1.
    """
    attempt = create_placement_attempt(request.user)
    return redirect("placement_written", attempt_id=attempt.id)


@login_required
@require_http_methods(["GET", "POST"])
def placement_written(request, attempt_id: int):
    """Step 1 of 2 — present 5 written questions and capture answers."""
    attempt = _user_attempt(request, attempt_id)
    questions = list(
        PlacementAttemptQuestion.objects.filter(
            attempt=attempt, section="written",
        ).select_related("question").order_by("order")
    )

    if request.method == "POST":
        for aq in questions:
            answer = (request.POST.get(f"q_{aq.id}") or "").strip()
            aq.user_answer_text = answer[:4000]
            aq.save(update_fields=["user_answer_text"])
        if attempt.status == "started":
            attempt.status = "written_completed"
            attempt.save(update_fields=["status"])
        # Part 2 is now a live voice call with the AI tutor; the old
        # MCQ-style speaking flow stays reachable via direct URL for
        # legacy attempts (and as a fallback if voice fails to start).
        return redirect("placement_voice_handoff", attempt_id=attempt.id)

    return render(request, "placement/written.html", {
        "attempt": attempt,
        "questions": questions,
        "step": 1,
        "total_steps": 2,
    })


@login_required
@require_http_methods(["GET", "POST"])
def placement_speaking(request, attempt_id: int):
    """Step 2 of 2 — present 5 speaking questions, capture transcripts.

    Audio recording happens client-side (Web Speech). We persist the
    transcript only by default; the schema supports an audio_file
    upload for future server-side STT.
    """
    attempt = _user_attempt(request, attempt_id)
    questions = list(
        PlacementAttemptQuestion.objects.filter(
            attempt=attempt, section="speaking",
        ).select_related("question").order_by("order")
    )

    if request.method == "POST":
        for aq in questions:
            transcript = (request.POST.get(f"q_{aq.id}_transcript") or "").strip()
            audio = request.FILES.get(f"q_{aq.id}_audio")
            update_fields = ["transcript"]
            if audio is not None:
                aq.audio_file = audio
                update_fields.append("audio_file")
                # Server-side STT fallback for browsers without the Web
                # Speech API (Firefox, iOS Safari). Only fires when the
                # client-side transcript is empty.
                if not transcript:
                    try:
                        from placement.services.stt import transcribe
                        audio.seek(0)
                        result = transcribe(audio) or {}
                        server_transcript = (result.get("transcript") or "").strip()
                        if server_transcript:
                            transcript = server_transcript
                    except Exception:
                        import logging
                        logging.getLogger(__name__).warning(
                            "placement speaking: server STT failed", exc_info=True,
                        )
            aq.transcript = transcript[:4000]
            aq.save(update_fields=update_fields)
        if attempt.status in ("started", "written_completed"):
            attempt.status = "speaking_completed"
            attempt.save(update_fields=["status"])
        _score_and_finalise(request, attempt)
        return redirect("placement_result", attempt_id=attempt.id)

    return render(request, "placement/speaking.html", {
        "attempt": attempt,
        "questions": questions,
        "step": 2,
        "total_steps": 2,
    })


@login_required
def placement_voice_handoff(request, attempt_id: int):
    """Start of placement Part 2 — create (or reuse) a TutorConversation
    tagged for placement and redirect into the voice-call page with a
    `?placement_attempt=N` flag so the call's hang-up routes back to
    `placement_voice_finalise` instead of the normal conversation
    detail page.
    """
    from tutor.models import TutorConversation
    attempt = _user_attempt(request, attempt_id)
    conv = attempt.voice_conversation
    if conv is None:
        conv = TutorConversation.objects.create(
            user=request.user,
            topic="placement",
            title=f"Placement #{attempt.id}",
        )
        attempt.voice_conversation = conv
        attempt.save(update_fields=["voice_conversation"])
    return redirect(
        f"/tutor/{conv.pk}/voice-call/?placement_attempt={attempt.id}"
    )


@login_required
def placement_voice_finalise(request, attempt_id: int):
    """Called from the voice-call screen after the student hangs up.

    Pulls the VoiceCallEvaluation written during the call, copies its
    scores onto the PlacementAttempt, marks it completed, then sends
    the student to the standard placement_result page.
    """
    from django.utils import timezone
    from tutor.models import VoiceCallEvaluation

    attempt = _user_attempt(request, attempt_id)
    conv = attempt.voice_conversation
    eval_obj = (
        VoiceCallEvaluation.objects.filter(conversation=conv).first()
        if conv is not None else None
    )
    if eval_obj is None:
        # The call ended too short to produce a transcript. Fall back to
        # the deterministic rule-based scorer so the student still gets
        # a level — they can retake from the result screen.
        _score_and_finalise(request, attempt)
        return redirect("placement_result", attempt_id=attempt.id)

    # Map voice-call eval scores onto the placement attempt schema.
    attempt.speaking_score = eval_obj.overall_score or 0
    attempt.fluency_score = eval_obj.fluency_score
    attempt.vocabulary_score = eval_obj.vocabulary_score
    attempt.grammar_score = eval_obj.grammar_score
    attempt.pronunciation_score = eval_obj.pronunciation_score
    # Written score was already captured during Step 1; recompute overall
    # as a 50/50 blend so both parts count.
    written = attempt.written_score or 0
    speaking = attempt.speaking_score or 0
    attempt.overall_score = int(round((written + speaking) / 2))
    attempt.recommended_cefr_level = eval_obj.cefr_level or "A1"
    attempt.feedback = eval_obj.summary or attempt.feedback
    attempt.status = "completed"
    attempt.completed_at = timezone.now()
    placement_result = PlacementResult.objects.create(
        user=request.user,
        level=attempt.recommended_cefr_level,
        written_score=written,
        speaking_score=speaking,
        grammar_score=attempt.grammar_score,
        vocabulary_score=attempt.vocabulary_score,
        fluency_score=attempt.fluency_score,
        pronunciation_score=attempt.pronunciation_score,
        overall_score=attempt.overall_score,
        feedback=attempt.feedback,
        transcript={"source": "voice_call", "conversation_id": conv.pk},
    )
    attempt.result = placement_result
    attempt.save(update_fields=[
        "written_score", "speaking_score", "grammar_score",
        "vocabulary_score", "fluency_score", "pronunciation_score",
        "overall_score", "recommended_cefr_level",
        "feedback", "status", "completed_at", "result",
    ])
    return redirect("placement_result", attempt_id=attempt.id)


@login_required
def placement_result(request, attempt_id: int):
    attempt = _user_attempt(request, attempt_id)
    written = list(
        attempt.questions.filter(section="written").select_related("question").order_by("order")
    )
    speaking = list(
        attempt.questions.filter(section="speaking").select_related("question").order_by("order")
    )
    return render(request, "placement/result.html", {
        "attempt": attempt,
        "written": written,
        "speaking": speaking,
    })


# ---------------------------------------------------------------------------
# Scoring + finalisation — wraps the existing AI assessor.
# ---------------------------------------------------------------------------

def _score_and_finalise(request, attempt: PlacementAttempt) -> None:
    """Run the AI assessor over the attempt's answers, record scores +
    final CEFR level, mark profile placed.

    Failure-tolerant: if the AI call crashes or returns garbage, we
    fall back to a deterministic rule-based score so the student still
    gets a level rather than an error page.
    """
    import logging
    log = logging.getLogger(__name__)

    result = score_placement_attempt(attempt, assessor=assess)

    written_score = int(result.get("written_score") or 0)
    speaking_score = int(result.get("speaking_score") or 0)
    grammar_score = result.get("grammar_score")
    vocabulary_score = result.get("vocabulary_score")
    fluency_score = result.get("fluency_score")
    pronunciation_score = result.get("pronunciation_score")
    overall_score = int(result.get("overall_score") or 0)
    level = result.get("recommended_cefr_level") or result.get("level") or "A1"

    attempt.written_score = written_score
    attempt.speaking_score = speaking_score
    attempt.grammar_score = grammar_score
    attempt.vocabulary_score = vocabulary_score
    attempt.fluency_score = fluency_score
    attempt.pronunciation_score = pronunciation_score
    attempt.overall_score = overall_score
    attempt.recommended_cefr_level = level
    attempt.feedback = result.get("feedback", "") or ""
    attempt.status = "completed"
    from django.utils import timezone
    attempt.completed_at = timezone.now()

    placement_result = PlacementResult.objects.create(
        user=request.user,
        level=level,
        written_score=written_score,
        speaking_score=speaking_score,
        grammar_score=grammar_score,
        vocabulary_score=vocabulary_score,
        fluency_score=fluency_score,
        pronunciation_score=pronunciation_score,
        overall_score=overall_score,
        feedback=result.get("feedback", "") or "",
        transcript=result.get("transcript") or {},
    )
    attempt.result = placement_result
    attempt.save(update_fields=[
        "written_score", "speaking_score", "grammar_score",
        "vocabulary_score", "fluency_score", "pronunciation_score",
        "overall_score",
        "recommended_cefr_level", "feedback", "status", "completed_at", "result",
    ])

    profile = request.user.profile
    profile.cefr_level = level
    if not profile.initial_cefr_level:
        profile.initial_cefr_level = level
    profile.placement_completed = True
    profile.save(update_fields=["cefr_level", "initial_cefr_level", "placement_completed"])

    try:
        from accounts.onboarding import complete_placement_onboarding
        complete_placement_onboarding(profile, level=level)
    except Exception:
        log.exception("complete_placement_onboarding failed")
    try:
        build_diagnostic_profile(
            request.user,
            result.get("diagnostic_answers") or {},
            assessment=result,
        )
    except Exception:
        log.exception("Diagnostic engine failed")
    try:
        from courses.services.student_flow import seed_level_course_recommendation
        seed_level_course_recommendation(request.user, level, source="placement")
    except Exception:
        log.exception("Placement course recommendation failed")
