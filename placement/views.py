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
    """Create a new attempt and redirect into the written step — or
    resume an unfinished one.

    Accepts GET (so a redirect from `onboarding_placement` lands cleanly
    in the browser) AND POST (the dashboard CTA form). If the student
    already has a placement attempt in progress, they are returned to
    the step they stopped at instead of starting the whole test over.
    """
    existing = (
        PlacementAttempt.objects
        .filter(user=request.user)
        .exclude(status="completed")
        .order_by("-started_at")
        .first()
    )
    if existing is not None:
        if existing.status == "started":
            return redirect("placement_written", attempt_id=existing.id)
        if existing.status == "written_completed":
            return redirect("placement_voice_handoff", attempt_id=existing.id)
        # speaking_completed — only the final scoring remains.
        return redirect("placement_result", attempt_id=existing.id)

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
        # Score the written section now (deterministic MCQ grading) so the
        # result page + dashboard never show 0/100 for a correct sheet.
        written_score = grade_written_section(attempt)
        if written_score is not None:
            attempt.written_score = written_score
            attempt.save(update_fields=["written_score"])
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
    from placement.services import speaking_quota
    attempt = _user_attempt(request, attempt_id)

    # One lifetime speaking attempt (Prompt 16.6F): if the student has
    # already used theirs (and no admin reset has reopened it), show a
    # friendly locked page instead of starting another call.
    allowed, code, message = speaking_quota.check_can_start(request.user)
    if not allowed:
        lang = getattr(request, "LANGUAGE_CODE", "en") or "en"
        text = (message or {}).get("ar" if str(lang).startswith("ar") else "en") \
            or (message or {}).get("en", "")
        return render(request, "placement/speaking_locked.html", {
            "message": text, "code": code, "attempt": attempt,
        }, status=403)

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


def grade_written_section(attempt: PlacementAttempt) -> int | None:
    """Grade the written section deterministically and persist per-question
    scores. Returns the 0-100 aggregate, or ``None`` when nothing gradable.

    MCQ questions are graded against the stored answer key (right=100,
    wrong=0). Open-ended written questions keep whatever AI/rubric score
    they already have. This is the single source of truth for
    ``attempt.written_score`` — without it the written score stays 0.
    """
    from placement.services.answer_key import is_answer_correct

    rows = list(
        attempt.questions.filter(section="written").select_related("question")
    )
    correct = counted = 0
    for aq in rows:
        q = aq.question
        verdict = is_answer_correct(
            (aq.user_answer_text or "").strip(),
            options=q.options, rubric=q.scoring_rubric,
            expected_type=q.expected_answer_type,
        )
        if verdict is None:
            if aq.score is not None:
                counted += 1
                correct += 1 if aq.score >= 50 else 0
            continue
        aq.score = 100.0 if verdict else 0.0
        aq.save(update_fields=["score"])
        counted += 1
        correct += 1 if verdict else 0
    if counted == 0:
        return None
    return int(round(100 * correct / counted))


def map_speaking_transcript(attempt: PlacementAttempt, conv, eval_obj) -> None:
    """Attach the student's spoken answers + a per-question score to each
    speaking question, so the result page can show what they actually said.

    The live call asks the 5 questions in order, so the i-th student turn
    maps to the i-th speaking question. Per-question score = 100 when the
    answer hits a rubric keyword, else the call's overall speaking score.
    """
    from tutor.models import TutorMessage

    rows = list(
        attempt.questions.filter(section="speaking")
        .select_related("question").order_by("order")
    )
    turns = list(
        TutorMessage.objects.filter(conversation=conv, role="user")
        .order_by("created_at").values_list("content", flat=True)
    ) if conv is not None else []
    overall = float((getattr(eval_obj, "overall_score", None) or 50))
    for i, aq in enumerate(rows):
        ans = (turns[i].strip() if i < len(turns) else "")
        rubric = aq.question.scoring_rubric or {}
        kws = [str(k).lower() for k in (rubric.get("voice_keywords") or [])]
        low = ans.lower()
        if not ans:
            score = 0.0
        elif kws and any(k in low for k in kws):
            score = 100.0
        else:
            score = overall
        aq.transcript = ans[:4000]
        aq.score = score
        aq.save(update_fields=["transcript", "score"])


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

    import logging
    log = logging.getLogger(__name__)

    # Map voice-call eval scores onto the placement attempt schema.
    attempt.speaking_score = eval_obj.overall_score or 0
    attempt.fluency_score = eval_obj.fluency_score
    attempt.vocabulary_score = eval_obj.vocabulary_score
    attempt.grammar_score = eval_obj.grammar_score
    attempt.pronunciation_score = eval_obj.pronunciation_score
    # Re-grade the written section deterministically (it may never have been
    # scored), and attach the student's spoken answers to each speaking
    # question so the result page shows them.
    written = grade_written_section(attempt)
    if written is None:
        written = attempt.written_score or 0
    map_speaking_transcript(attempt, conv, eval_obj)
    speaking = attempt.speaking_score or 0
    attempt.written_score = written
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

    # Keep the profile + onboarding + diagnostic email CONSISTENT with what
    # the dashboard shows: the email must report the SAME level/scores as
    # this result (previously it ran a separate assessor and could disagree,
    # e.g. email B1 vs dashboard A2).
    level = attempt.recommended_cefr_level
    try:
        profile = request.user.profile
        profile.cefr_level = level
        if not profile.initial_cefr_level:
            profile.initial_cefr_level = level
        profile.placement_completed = True
        profile.save(update_fields=["cefr_level", "initial_cefr_level", "placement_completed"])
    except Exception:
        log.exception("placement_voice_finalise: profile update failed")
    try:
        from accounts.onboarding import complete_placement_onboarding
        complete_placement_onboarding(request.user.profile, level=level)
    except Exception:
        log.exception("placement_voice_finalise: onboarding failed")
    try:
        diag_answers = {
            "mode": "dynamic",
            "items": [
                {"section": "written", "answer": aq.user_answer_text,
                 "expected_answer_type": aq.question.expected_answer_type}
                for aq in attempt.questions.filter(section="written").select_related("question")
            ],
        }
        build_diagnostic_profile(request.user, diag_answers, assessment={
            "level": level,
            "written_score": written,
            "speaking_score": speaking,
            "grammar_score": attempt.grammar_score,
            "vocabulary_score": attempt.vocabulary_score,
            "fluency_score": attempt.fluency_score,
            "pronunciation_score": attempt.pronunciation_score,
            "overall_score": attempt.overall_score,
            "feedback": attempt.feedback,
        })
    except Exception:
        log.exception("placement_voice_finalise: diagnostic/email failed")
    return redirect("placement_result", attempt_id=attempt.id)


@login_required
def placement_result(request, attempt_id: int):
    from placement.services.answer_key import correct_answer_for, is_answer_correct

    attempt = _user_attempt(request, attempt_id)
    written = list(
        attempt.questions.filter(section="written").select_related("question").order_by("order")
    )
    speaking = list(
        attempt.questions.filter(section="speaking").select_related("question").order_by("order")
    )

    def _annotate(rows):
        for aq in rows:
            q = aq.question
            student = aq.user_answer_text if aq.section == "written" else aq.transcript
            aq.student_answer = (student or "").strip()
            aq.correct_answer = correct_answer_for(
                options=q.options, rubric=q.scoring_rubric, expected_type=q.expected_answer_type,
            )
            verdict = is_answer_correct(
                aq.student_answer, options=q.options, rubric=q.scoring_rubric,
                expected_type=q.expected_answer_type,
            )
            # Deterministic key wins; otherwise fall back to the rubric/AI
            # score (>= 50 = pass) so the student still gets a ✓/✗ signal.
            if verdict is None:
                verdict = (aq.score is not None and aq.score >= 50) if aq.student_answer else False
            aq.is_correct_display = verdict
        return rows

    return render(request, "placement/result.html", {
        "attempt": attempt,
        "written": _annotate(written),
        "speaking": _annotate(speaking),
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
