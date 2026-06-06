import json
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from .models import (
    PlacementAttempt, PlacementAttemptQuestion, PlacementResult,
)

logger = logging.getLogger(__name__)
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
def placement(request):
    """Entry point for the placement test.

    The old single-page flow used hard-coded questions that ignored the
    admin-managed question bank — so the test never showed the ACTIVE
    questions the admin selected. It is retired: everyone is routed to the
    curated dynamic flow (`placement_start` → written MCQ from the active
    bank → speaking voice call → result). Completed students see their
    latest result instead.
    """
    profile = request.user.profile
    if not profile.placement_completed or request.session.get("placement_retake"):
        return redirect("placement_start")
    latest = (
        PlacementResult.objects.filter(user=request.user)
        .order_by("-created_at").first()
    )
    history = list(
        PlacementResult.objects.filter(user=request.user)
        .order_by("-created_at")[:10]
    )
    return render(request, "placement/already_taken.html", {
        "profile": profile, "latest": latest, "history": history,
    })


def _legacy_placement_disabled(request):
    """Old hard-coded single-page handler — retained only as dead reference."""
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
    # The retake flag only gated the retired legacy page; clear it so the
    # entry view doesn't bounce back here forever after a retake.
    request.session.pop("placement_retake", None)
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


@login_required
@require_POST
def placement_speaking_answer(request, attempt_id: int):
    """LIVE per-question answer save during the speaking call.

    The browser POSTs the FINAL student transcript together with the explicit
    ``question_id`` that was being asked at that moment, so the answer is bound
    at listening time — never reconstructed from the whole conversation. Tutor /
    opening / "Right?" text and answers without a question_id are rejected.
    """
    from placement.services import speaking_alignment as sa
    attempt = _user_attempt(request, attempt_id)
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        payload = {}
    qid = payload.get("question_id")
    transcript = (payload.get("transcript") or "").strip()
    if not qid:
        return JsonResponse({"ok": False, "error": "missing_question_id"}, status=400)
    # The question must belong to THIS user's attempt (ownership first).
    aq = (
        attempt.questions.filter(section="speaking", id=qid)
        .select_related("question").first()
    )
    if aq is None:
        return JsonResponse({"ok": False, "error": "bad_question"}, status=404)
    if not transcript:
        return JsonResponse({"ok": False, "error": "empty"}, status=400)
    # Never store tutor / greeting / "Right?" / "Great" as a student answer.
    if sa.is_greeting_or_closing(transcript):
        return JsonResponse({"ok": True, "skipped": "pleasantry"})
    clause = sa.extract_relevant_answer_for_question(aq.question, transcript)
    if not clause:
        return JsonResponse({"ok": True, "skipped": "no_clause"})
    existing = (aq.transcript or "").strip()
    if existing and clause.lower() in existing.lower():
        # Idempotent upsert: the same clause re-sent (network retry) is a no-op.
        return JsonResponse({"ok": True, "question_id": aq.id, "order": aq.order, "dedup": True})
    aq.transcript = (existing + " " + clause).strip() if existing else clause
    aq.save(update_fields=["transcript"])
    logger.info(
        "placement live answer saved attempt=%s q=%s order=%s len=%s",
        attempt.id, aq.id, aq.order, len(aq.transcript),
    )
    return JsonResponse({"ok": True, "question_id": aq.id, "order": aq.order})


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


_SPK_STOP = {
    "what", "is", "are", "you", "your", "do", "does", "did", "for", "an",
    "the", "to", "why", "where", "how", "of", "in", "on", "at", "and", "or",
    "with", "am", "me", "my", "we", "they", "this", "that", "tell", "about",
    "please", "can", "could", "would", "now", "let", "next", "question",
    "okay", "great", "good", "thanks", "thank", "hello", "welcome", "start",
}


def _spk_keywords(text: str) -> list[str]:
    """Distinctive content tokens of a question (drops stop words)."""
    import re
    toks = re.findall(r"[a-z]+", (text or "").lower())
    return [t for t in toks if len(t) > 2 and t not in _SPK_STOP]


def _spk_overlap(keywords: list[str], text: str) -> int:
    low = (text or "").lower()
    return sum(1 for k in keywords if k in low)


# Pure social pleasantries that are NEVER a real placement answer (greeting /
# goodbye / thanks). Matched only when they are the WHOLE reply.
_PLEASANTRIES = {
    "hi", "hello", "hey", "bye", "goodbye", "ok", "okay", "thanks",
    "thank you", "thank you so much", "thanks a lot", "good bye",
    "see you", "nice to meet you", "no problem", "you too",
}


def _is_pleasantry(text: str) -> bool:
    import re
    t = re.sub(r"[^a-z\s]", "", (text or "").lower()).strip()
    t = re.sub(r"\s+", " ", t)
    return t in _PLEASANTRIES


def _question_cues(question) -> set[str]:
    """Distinctive cue words that identify WHICH fixed placement question a
    tutor turn is asking. Deliberately avoids generic words (do/where/english)
    that also appear in the opening so the auto-start greeting can't be
    mistaken for a later question."""
    t = (question.question_text or "").lower()
    if "name" in t:
        return {"name"}
    if "old" in t or "age" in t:
        return {"old", "age"}
    if "from" in t or "country" in t or "nationality" in t:
        return {"from", "country", "nationality"}
    if "living" in t or "do you do" in t or "work" in t or "job" in t:
        return {"living", "work", "job", "profession", "occupation"}
    if "learn" in t or "why" in t:
        return {"learn", "reason", "why"}
    return set(_spk_keywords(question.question_text))


def _question_asked_in(question, text: str) -> bool:
    low = (text or "").lower()
    return any(cue in low for cue in _question_cues(question))


def compute_speaking_score(attempt: PlacementAttempt, *, fallback: int = 0) -> int:
    """Mean of the per-question speaking scores (0-100), or ``fallback`` when
    none are scored yet."""
    scores = [
        r.score for r in attempt.questions.filter(section="speaking")
        if r.score is not None
    ]
    if not scores:
        return int(fallback or 0)
    return int(round(sum(scores) / len(scores)))


def map_speaking_transcript(attempt: PlacementAttempt, conv, eval_obj, *,
                            use_live: bool = True) -> None:
    """Score each speaking question from the student's answer.

    Binding is PER QUESTION (not all-or-nothing): every question that already
    has a LIVE transcript (saved during the call with its question_id) keeps it
    untouched; only the MISSING questions are backfilled from their own slot in
    the fallback state machine. So a partial live capture (only Q1 saved) never
    leaves Q2-Q5 wrong, and the fallback never smears the whole conversation
    over the answers that ARE correctly bound.
    """
    from tutor.models import TutorMessage
    from placement.services import speaking_alignment as sa
    from placement.services.speaking_eval import score_speaking_answers

    rows = list(
        attempt.questions.filter(section="speaking")
        .select_related("question").order_by("order")
    )

    # --- Live coverage, computed PER QUESTION ---
    live = [(r.transcript or "").strip() for r in rows]
    total = len(rows)
    live_count = sum(1 for a in live if a)
    missing_idx = [i for i, a in enumerate(live) if not a]
    logger.info(
        "placement speaking coverage attempt=%s total=%s live=%s missing_q=%s",
        attempt.id, total, live_count, [rows[i].id for i in missing_idx],
    )

    need_fallback = (not use_live) or (live_count == 0) or bool(missing_idx)
    fb = None
    if need_fallback:
        turns = (
            list(TutorMessage.objects.filter(conversation=conv)
                 .order_by("created_at", "id").values("role", "content"))
            if conv is not None else []
        )
        fb, warnings = sa.align_answers_by_explicit_question_state(rows, turns)
        for w in warnings:
            logger.warning("placement align (attempt=%s): %s", attempt.id, w)

    if not use_live or live_count == 0:
        # No trustworthy live answers → full fallback for every question.
        answers = fb
    else:
        # Hybrid: keep each correctly-bound live answer; backfill ONLY the
        # missing questions from their OWN fallback slot.
        answers = [live[i] if live[i] else (fb[i] if fb else "") for i in range(total)]

    # Meaning-based scoring (forgives minor grammar / missing-article slips);
    # one batched AI call, with a lenient heuristic fallback offline.
    graded = score_speaking_answers(
        [((aq.question.question_text or ""), answers[ri]) for ri, aq in enumerate(rows)]
    )
    for ri, aq in enumerate(rows):
        g = graded[ri] if ri < len(graded) else {"score": 0, "feedback": ""}
        aq.transcript = answers[ri][:4000]
        aq.score = float(g.get("score") or 0)
        aq.feedback = (g.get("feedback") or "")[:500]
        aq.save(update_fields=["transcript", "score", "feedback"])


def _speaking_retry_message(request, answered: int) -> str:
    """Bilingual friendly message for the strict speaking gate."""
    lang = getattr(request, "LANGUAGE_CODE", "en") or "en"
    ar = (
        "يرجى إكمال جزء التحدث قبل عرض النتيجة النهائية."
        if answered == 0 else
        "لم نتمكن من سماع إجابتك بوضوح. حاول مرة أخرى."
    )
    en = (
        "Please complete the speaking section before viewing your final result."
        if answered == 0 else
        "We could not hear your answer clearly. Please try again."
    )
    return ar if str(lang).startswith("ar") else en


def _speaking_system_error_message(request) -> str:
    lang = getattr(request, "LANGUAGE_CODE", "en") or "en"
    if str(lang).startswith("ar"):
        return "حدث خطأ تقني أثناء تقييم إجابتك. لم نخصم أي رصيد. يرجى المحاولة مرة أخرى."
    return ("A technical problem occurred while scoring your answer. "
            "Nothing was charged. Please try again.")


def _clear_partial_call(conv):
    """Wipe a partial placement call so the retry starts fresh."""
    if conv is None:
        return
    try:
        from tutor.models import TutorMessage, VoiceCallEvaluation
        TutorMessage.objects.filter(conversation=conv).delete()
        VoiceCallEvaluation.objects.filter(conversation=conv).delete()
    except Exception:
        pass


def _mark_speaking_failed_system(request, attempt, conv) -> None:
    """Technical failure path: never finalise, never consume minutes, retry."""
    from placement.services import speaking_quota
    if conv is not None:
        speaking_quota.mark_failed_system(attempt, conv)
        _clear_partial_call(conv)
    attempt.questions.filter(section="speaking").update(transcript="", score=None)
    attempt.status = "written_completed"
    attempt.save(update_fields=["status"])


def _finalise_speaking_unable(request, attempt, conv, answered: int):
    """The student was asked the questions but couldn't answer after retries.

    This is NOT a technical failure — it's evidence of very low speaking
    ability. Finalise CONSERVATIVELY (speaking A0, overall capped) so a true
    beginner is never blocked forever.
    """
    import logging
    from django.conf import settings as _dj
    from django.utils import timezone
    from placement.services import speaking_quota
    from placement.services.level_mapping import level_for_percentage, cap_level
    log = logging.getLogger(__name__)

    written = grade_written_section(attempt)
    if written is None:
        written = attempt.written_score or 0
    unable_level = getattr(_dj, "PLACEMENT_SPEAKING_UNABLE_LEVEL", "A0")
    cap = getattr(_dj, "PLACEMENT_FINAL_CAP_WHEN_UNABLE", "A1")
    level = cap_level(level_for_percentage(written), cap)

    attempt.speaking_score = 0
    attempt.written_score = written
    attempt.overall_score = int(round(written / 2))  # speaking counts as 0
    attempt.recommended_cefr_level = level
    attempt.feedback = (attempt.feedback or "")
    attempt.status = "completed"
    attempt.completed_at = timezone.now()
    result = PlacementResult.objects.create(
        user=attempt.user, level=level, written_score=written, speaking_score=0,
        overall_score=attempt.overall_score,
        feedback="Speaking: unable to answer after retries — conservative placement.",
        transcript={"source": "voice_call", "speaking_status": "unable_to_answer_after_retries",
                    "speaking_level": unable_level, "answered": answered},
    )
    attempt.result = result
    attempt.save(update_fields=[
        "speaking_score", "written_score", "overall_score",
        "recommended_cefr_level", "feedback", "status", "completed_at", "result",
    ])
    if conv is not None:
        speaking_quota.mark_unable(attempt, conv, answered)
    # Profile + course (so the learner moves forward), best-effort.
    try:
        profile = attempt.user.profile
        profile.cefr_level = level
        if not profile.initial_cefr_level:
            profile.initial_cefr_level = level
        profile.placement_completed = True
        profile.save(update_fields=["cefr_level", "initial_cefr_level", "placement_completed"])
        from accounts.onboarding import complete_placement_onboarding
        complete_placement_onboarding(profile, level=level)
    except Exception:
        log.warning("placement: unable-finalise profile/course failed", exc_info=True)
    return redirect("placement_result", attempt_id=attempt.id)


def _block_speaking_and_retry(request, attempt, conv, answered: int) -> None:
    """Strict gate: do NOT finalise. Reset the speaking section for a clean
    retry and mark the speaking attempt retryable (lifetime attempt kept)."""
    from placement.services import speaking_quota
    # Mark the speaking attempt needs_retry / failed_start (is_used=False).
    if conv is not None:
        speaking_quota.mark_needs_retry(attempt, conv, answered)
        # Clear the partial call so the retry starts fresh (placement-only conv).
        try:
            from tutor.models import TutorMessage, VoiceCallEvaluation
            TutorMessage.objects.filter(conversation=conv).delete()
            VoiceCallEvaluation.objects.filter(conversation=conv).delete()
        except Exception:
            pass
    # Wipe any partial transcripts/scores; keep the attempt at the speaking step.
    attempt.questions.filter(section="speaking").update(transcript="", score=None)
    attempt.status = "written_completed"
    attempt.save(update_fields=["status"])


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
    import logging
    log = logging.getLogger(__name__)
    from placement.services import completion

    # Map whatever was captured so we can BOTH display it and judge whether the
    # speaking section is complete enough to finalise.
    map_speaking_transcript(attempt, conv, eval_obj)
    answered = completion.count_speaking_answers(attempt)

    # STRICT-BUT-SAFE GATE. Three distinct outcomes (the student never starts —
    # the tutor asks every question; this only judges what came back):
    if completion.require_speaking():
        if eval_obj is None:
            # (6) TECHNICAL failure (STT / provider / system). NOT the student's
            # fault — never finalise, never consume minutes, always retryable.
            _mark_speaking_failed_system(request, attempt, conv)
            messages.warning(request, _speaking_system_error_message(request))
            return redirect("placement_voice_handoff", attempt_id=attempt.id)

        if answered < completion.min_answers():
            # The system worked but the student answered too few. Decide between
            # "give them another try" and "they genuinely can't answer".
            questions_asked = completion.count_questions_asked(conv)
            attempt.speaking_retry_count = (attempt.speaking_retry_count or 0) + 1
            attempt.save(update_fields=["speaking_retry_count"])
            exhausted = attempt.speaking_retry_count >= completion.max_retries()
            tutor_asked_all = questions_asked >= completion.min_answers()
            if tutor_asked_all or exhausted:
                # (B) unable_to_answer_after_retries → conservative finalise so a
                # true beginner is NEVER blocked forever.
                return _finalise_speaking_unable(request, attempt, conv, answered)
            # Otherwise let them try again.
            _block_speaking_and_retry(request, attempt, conv, answered)
            messages.warning(request, _speaking_retry_message(request, answered))
            return redirect("placement_voice_handoff", attempt_id=attempt.id)

    if eval_obj is None:
        # Gate disabled via settings → legacy graceful fallback so the student
        # still receives a level rather than an error page.
        _score_and_finalise(request, attempt)
        return redirect("placement_result", attempt_id=attempt.id)

    # ---- (A) completed_by_answers → finalise (scores, result, course, email) ----
    # Speaking score = mean of the per-question MEANING-based scores (set by
    # map_speaking_transcript), so the headline number matches the per-answer
    # badges instead of a separate, harsher figure.
    attempt.speaking_score = compute_speaking_score(attempt, fallback=eval_obj.overall_score or 0)
    attempt.fluency_score = eval_obj.fluency_score
    attempt.vocabulary_score = eval_obj.vocabulary_score
    attempt.grammar_score = eval_obj.grammar_score
    attempt.pronunciation_score = eval_obj.pronunciation_score
    written = grade_written_section(attempt)
    if written is None:
        written = attempt.written_score or 0
    # Best-effort: cache each oral question's "Other possible answers"
    # (free for the starter bank; never charges AI-Tutor minutes).
    try:
        from placement.services.ai_alternatives import ensure_alternatives
        for aq in attempt.questions.filter(section="speaking").select_related("question"):
            ensure_alternatives(aq.question)
    except Exception:
        log.warning("placement: alternatives prefetch failed", exc_info=True)
    speaking = attempt.speaking_score or 0
    attempt.written_score = written
    attempt.overall_score = int(round((written + speaking) / 2))
    # Product policy: the OVERALL score maps DIRECTLY to the CEFR level
    # (A0..C2) via PLACEMENT_LEVEL_MAP — score-based placement, no difficulty
    # cap. e.g. 96-100 → C2, 41-60 → A2. (The AI's own cefr estimate is NOT
    # used for the final level.)
    from placement.services.level_mapping import level_for_percentage
    attempt.recommended_cefr_level = level_for_percentage(attempt.overall_score)
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
    from placement.services import completion

    attempt = _user_attempt(request, attempt_id)

    # STRICT GATE: the final result requires a completed speaking section.
    # If it isn't finalised, send the student to complete speaking instead of
    # showing an empty / partial result.
    if completion.require_speaking() and not completion.is_finalised(attempt):
        messages.warning(request, _speaking_retry_message(request, completion.count_speaking_answers(attempt)))
        return redirect("placement_voice_handoff", attempt_id=attempt.id)

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
            # Oral guidance only: "Other possible answers" (never grading).
            if aq.section == "speaking":
                from placement.services.ai_alternatives import alternatives_for
                aq.alternatives = alternatives_for(q, student_transcript=aq.student_answer)
            else:
                aq.alternatives = []
        return rows

    from placement.services.level_mapping import level_for_percentage
    return render(request, "placement/result.html", {
        "attempt": attempt,
        "written": _annotate(written),
        "speaking": _annotate(speaking),
        # The speaking LEVEL follows the speaking SCORE directly (same A0..C2
        # mapping as the final level) — score-based, no difficulty cap.
        "speaking_level": level_for_percentage(attempt.speaking_score or 0),
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
    # Product policy: the OVERALL score maps DIRECTLY to the CEFR level (A0..C2)
    # via PLACEMENT_LEVEL_MAP — score-based placement, no difficulty cap. The
    # assessor's own level estimate is NOT used for the final level.
    from placement.services.level_mapping import level_for_percentage
    level = level_for_percentage(overall_score)

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
