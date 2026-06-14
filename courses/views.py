from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods, require_POST

from accounts.decorators import subscription_required

from .models import CourseLessonProgress
from .services.a0_world import build_a0_world, is_a0_course
from .services.lesson_gate import annotate_lesson_states, can_open_lesson
from .services.student_flow import (
    can_access_course,
    can_access_lesson,
    ensure_course_enrollment,
    published_course_queryset,
    published_lesson_queryset,
)


def _drip_gate(request, course, lesson):
    """Return a redirect response when ``lesson`` is still drip-locked
    for the requesting student, else ``None``.

    Course access (subscription) is assumed already verified by the
    caller — this guards only the sequential daily unlock so a locked
    lesson cannot be reached via a hand-typed URL or a crafted POST.
    """
    if can_open_lesson(course=course, lesson=lesson, user=request.user, has_access=True):
        return None
    messages.info(request, _(
        "This lesson is still locked. Finish the previous lesson first — "
        "the next one opens a day later."
    ))
    return redirect("courses:course_detail", pk=course.pk)


def _notify_teacher_low_performance(course, student, lesson, score):
    """Flag a struggling student to the course's teacher when they fail
    a lesson quiz — deduped to one notice per (teacher, student) per day
    so a teacher isn't spammed. Best-effort; never blocks the response.
    """
    teacher = getattr(course, "teacher", None)
    if teacher is None or teacher.id == student.id:
        return
    try:
        from datetime import timedelta

        from notifications import constants as notif_constants
        from notifications.models import NotificationEvent
        from teacher_portal.services.notification_service import create_teacher_notification

        since = timezone.now() - timedelta(hours=24)
        recent = NotificationEvent.objects.filter(
            user=teacher,
            event_type=notif_constants.TEACHER_STUDENT_LOW_PERFORMANCE,
            created_at__gte=since,
        )
        for event in recent:
            if (event.payload or {}).get("student_id") == student.id:
                return  # already flagged this student today
        create_teacher_notification(
            teacher=teacher,
            actor=student,
            event_type=notif_constants.TEACHER_STUDENT_LOW_PERFORMANCE,
            payload={
                "student_id": student.id,
                "lesson_id": lesson.id,
                "lesson_title": lesson.title,
                "score": score,
            },
        )
    except Exception:
        import logging
        logging.getLogger(__name__).warning(
            "low-performance teacher notice failed", exc_info=True,
        )


@login_required
def course_detail(request, pk):
    course = get_object_or_404(published_course_queryset(), pk=pk)
    has_access = can_access_course(request.user, course)
    enrollment = ensure_course_enrollment(request.user, course) if has_access else None
    lessons = list(published_lesson_queryset().filter(course=course))
    is_a0_world = is_a0_course(course)
    a0_world = (
        build_a0_world(course=course, lessons=lessons, user=request.user, has_access=has_access)
        if is_a0_world else None
    )
    # Non-A0 courses: sequential daily-drip state per lesson. A0 courses
    # carry their unlock state inside `a0_world` instead.
    lesson_rows = (
        None if is_a0_world else
        annotate_lesson_states(
            course=course, lessons=lessons,
            user=request.user, has_access=has_access,
        )
    )
    # Roadmap progress — how far the student is along the course.
    lesson_progress = None
    if lesson_rows is not None:
        total = len(lesson_rows)
        done = sum(1 for r in lesson_rows if r["is_completed"])
        lesson_progress = {
            "done": done,
            "total": total,
            "pct": round(done * 100 / total) if total else 0,
        }

    # Weekly Review gate (Prompt 18.3D) — read-only recommendation: units whose
    # 3 lessons are all done. Never writes progress, never blocks the learner.
    pending_weekly = []
    if has_access:
        try:
            from .services.weekly_review_gate import pending_weekly_reviews
            pending_weekly = pending_weekly_reviews(request.user, course)
        except Exception:
            pending_weekly = []

    return render(request, "courses/detail.html", {
        "course": course,
        "lessons": lessons,
        "lesson_rows": lesson_rows,
        "lesson_progress": lesson_progress,
        "has_access": has_access,
        "enrollment": enrollment,
        "is_a0_world": is_a0_world,
        "a0_world": a0_world,
        "pending_weekly_reviews": pending_weekly,
    })


@login_required
def course_lesson_detail(request, course_pk, lesson_pk):
    course = get_object_or_404(published_course_queryset(), pk=course_pk)
    lesson = get_object_or_404(
        published_lesson_queryset().filter(course=course),
        pk=lesson_pk,
    )
    if not can_access_lesson(request.user, lesson):
        return HttpResponseForbidden(_("An active subscription is required for this lesson."))

    enrollment = ensure_course_enrollment(request.user, course)
    drip_redirect = _drip_gate(request, course, lesson)
    if drip_redirect:
        return drip_redirect
    progress, _created = CourseLessonProgress.objects.get_or_create(
        user=request.user, lesson=lesson,
    )

    quiz = None
    try:
        quiz = lesson.quiz
    except Exception:
        quiz = None

    # Next-unit CTA on the lesson page links to the next ordered Lesson in
    # the same course. Falls back to None when this is the last lesson.
    next_lesson = (
        published_lesson_queryset()
        .filter(course=course, order__gt=lesson.order)
        .order_by("order")
        .first()
    )

    # Step cards consumed by the overview template. Tuples of
    # (kind, emoji, en_title, ar_title, en_sub, ar_sub) — order = the
    # learner's path through the stepper.
    step_cards = [
        ("intro",      "🎬", "Introduction", "مقدمة",
         "Listen to the welcome", "استمع للترحيب"),
        ("vocabulary", "📖", "Vocabulary", "المفردات",
         "Learn the key words", "تعلّم الكلمات الجديدة"),
        ("examples",   "💡", "Examples", "أمثلة",
         "Hear it in context", "اسمعها في السياق"),
        ("dialogue",   "💬", "Dialogue", "حوار",
         "Two characters talking", "شخصان يتحدثان"),
        ("listening",  "🎧", "Listening", "استماع",
         "Focus on the sounds", "ركّز على الأصوات"),
        ("speaking",   "🗣", "Speaking", "محادثة",
         "Your turn to speak", "دورك للحديث"),
        ("finish",     "🏁", "Finish", "إنهاء",
         "Quiz + checklist", "كويز وقائمة"),
    ]

    # Surface the state of the user's most-recent challenge session so the
    # launcher can switch label between Start / Resume / Practice again.
    active_challenge = None
    last_challenge = None
    if quiz is not None:
        from .models import ChallengeSession
        active_challenge = (
            ChallengeSession.objects.filter(
                user=request.user, lesson=lesson,
                status__in=("started", "in_progress"),
            ).order_by("-updated_at").first()
        )
        last_challenge = (
            ChallengeSession.objects.filter(user=request.user, lesson=lesson)
            .order_by("-updated_at").first()
        )

    return render(request, "courses/lesson_detail.html", {
        "course": course,
        "lesson": lesson,
        "enrollment": enrollment,
        "video": lesson.get_video_embed(),
        "progress": progress,
        "quiz": quiz,
        "next_lesson": next_lesson,
        "step_cards": step_cards,
        "active_challenge": active_challenge,
        "last_challenge": last_challenge,
    })


# Ordered taxonomy of lesson steps. The view + template branch on this
# tuple — adding "review" or another stage means editing this and the
# step template's CONFIG dict only.
LESSON_STEP_KINDS = (
    "intro", "vocabulary", "examples", "dialogue", "listening", "speaking",
    "finish",
)


def _parse_vocabulary(text: str) -> list[dict]:
    """Parse a vocabulary script into per-topic groups of individual words.

    Each topic is separated by ";" (rendered on its own line). The words to
    "listen and repeat" are the comma-separated tokens, taken from:
      1. inside "(...)" when present, else
      2. after the last ":" (e.g. "...objects: laptop, charger, ..."), else
      3. a bare comma list, else
      4. the whole segment as a single item (no list at all).
    Trailing "Listen and repeat ..." instructions are stripped from the words.
    Works for ANY vocabulary script — no per-course assumptions.

    Example: "16 daily objects: laptop, charger, glasses. Listen and repeat."
        → [{"label": "16 daily objects", "words": ["laptop","charger","glasses"]}]
    """
    import re

    _instr = re.compile(r"[.,]?\s*listen\s+and\s+repeat\b[^.]*\.?\s*$", re.IGNORECASE)

    def _clean_word(w: str) -> str:
        w = w.strip().strip(".…").strip()
        # Drop placeholder tokens ("…", "...", "etc") — not real words to speak.
        if not w or not any(ch.isalnum() for ch in w) or w.lower() in {"etc", "and so on"}:
            return ""
        return w

    groups: list[dict] = []
    for segment in (s.strip() for s in text.split(";")):
        if not segment:
            continue
        seg = _instr.sub("", segment).strip()   # drop a trailing "Listen and repeat …"
        if not seg:
            continue
        words_str = None
        label = ""
        m = re.search(r"\(([^)]*)\)", seg)
        if m:
            label = seg[: m.start()].strip().rstrip(":").strip()
            words_str = m.group(1)
        elif ":" in seg and "," in seg.rsplit(":", 1)[1]:
            label, words_str = seg.rsplit(":", 1)
            label = label.strip()
        elif "," in seg:
            words_str = seg
        words = [w for w in (_clean_word(x) for x in (words_str or "").split(",")) if w]
        if len(words) >= 2:
            # A real word list → speak the (optional) label, then each word.
            groups.append({"kind": "words", "label": label, "words": words, "text": ""})
        else:
            # Plain sentence → render and speak it as one line.
            groups.append({"kind": "line", "label": "", "words": [], "text": seg})
    return groups


@login_required
def lesson_step(request, course_pk, lesson_pk, step_kind):
    """Render ONE step of a lesson stepper as its own page.

    Each step gets a dedicated URL so the student can deep-link, the
    browser back/forward buttons work, and the page can be fully
    immersive (no off-step distractions in the DOM).

    `step_kind` is one of `LESSON_STEP_KINDS`. The first six map onto a
    `LessonAudioScript.script_type`; the final `finish` step has no
    audio — it's the wrap-up (checklist + quiz + next-unit CTAs).
    """
    if step_kind not in LESSON_STEP_KINDS:
        raise Http404("Unknown step")

    course = get_object_or_404(published_course_queryset(), pk=course_pk)
    lesson = get_object_or_404(
        published_lesson_queryset().filter(course=course),
        pk=lesson_pk,
    )
    if not can_access_lesson(request.user, lesson):
        return HttpResponseForbidden(_("An active subscription is required for this lesson."))

    drip_redirect = _drip_gate(request, course, lesson)
    if drip_redirect:
        return drip_redirect

    progress, _ = CourseLessonProgress.objects.get_or_create(
        user=request.user, lesson=lesson,
    )

    # Pull the audio script for this step (None for `finish`).
    script = None
    dialogue_turns: list[tuple[str, str]] = []
    example_lines: list[str] = []
    listen_repeat_groups: list[dict] = []
    if step_kind != "finish":
        script = lesson.audio_scripts.filter(script_type=step_kind).first()
        if script and script.script_text:
            text = script.script_text.strip()
            # Dialogue: each line is "Speaker: line text". Split into
            # tuples for chat-bubble rendering. A line without ": " is
            # treated as narration (speaker = "").
            if step_kind == "dialogue":
                for raw in text.splitlines():
                    raw = raw.strip()
                    if not raw:
                        continue
                    if ":" in raw and len(raw.split(":", 1)[0]) <= 24:
                        spk, line = raw.split(":", 1)
                        dialogue_turns.append((spk.strip(), line.strip()))
                    else:
                        dialogue_turns.append(("", raw))
            # Examples: one example sentence per line.
            elif step_kind == "examples":
                example_lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
            # Vocabulary + Intro + Listening + Speaking: parse into "listen and
            # repeat" groups so each vocabulary WORD (inside "(...)" or a comma
            # list) is spoken on its own with a gap, while narrative sentences /
            # task instructions stay whole. Listening & speaking carry an
            # instruction sentence — without this branch their step rendered
            # silent (no Listen button, no audio). Global — works for any
            # script in any course/lesson.
            elif step_kind in ("vocabulary", "intro", "listening", "speaking"):
                listen_repeat_groups = _parse_vocabulary(text)

    # Compute prev/next step kinds for the navigation pills.
    idx = LESSON_STEP_KINDS.index(step_kind)
    prev_kind = LESSON_STEP_KINDS[idx - 1] if idx > 0 else None
    next_kind = LESSON_STEP_KINDS[idx + 1] if idx + 1 < len(LESSON_STEP_KINDS) else None

    # Cover image (LessonImagePrompt of type "cover").
    cover_prompt = (
        lesson.image_prompts.filter(prompt_type="cover", is_generated=True)
        .order_by("sort_order").first()
    )

    # Phase 9.5: Pick the step-relevant LessonImagePrompt — used by the
    # template to render either a real `<img>` or a friendly "coming
    # soon" placeholder. This keeps the visual promise of every step
    # honest even before media batches run.
    step_prompt_map = {
        "vocabulary": "vocabulary",
        "examples":   "grammar",
        "dialogue":   "grammar",
        "finish":     "quiz",
    }
    image_prompt_for_step = None
    pt = step_prompt_map.get(step_kind)
    if pt:
        image_prompt_for_step = (
            lesson.image_prompts.filter(prompt_type=pt)
            .order_by("sort_order").first()
        )

    # Audio is shown to the student ONLY when approved AND the file truly
    # exists in storage — an approved row whose file went missing must fall
    # back to the clean placeholder (never a broken <audio>), and we log it
    # so admins can spot it via inspect_lesson_media.
    audio_ready = False
    if script is not None and script.is_student_visible:
        af = script.generated_audio
        try:
            audio_ready = bool(af) and af.storage.exists(af.name)
        except Exception:
            audio_ready = False
        if not audio_ready:
            logging.getLogger(__name__).warning(
                "lesson_step: approved audio file missing for lesson=%s step=%s name=%s",
                lesson.pk, step_kind, getattr(af, "name", ""),
            )

    quiz = None
    try:
        quiz = lesson.quiz
    except Exception:
        quiz = None

    next_lesson = (
        published_lesson_queryset()
        .filter(course=course, order__gt=lesson.order)
        .order_by("order").first()
    )

    from django.conf import settings as _dj_settings
    return render(request, "courses/lesson_step.html", {
        "course": course,
        "lesson": lesson,
        "progress": progress,
        "script": script,
        "audio_ready": audio_ready,
        "dialogue_turns": dialogue_turns,
        "example_lines": example_lines,
        "listen_repeat_groups": listen_repeat_groups,
        # Examples "listen and repeat" pacing (global, configurable via settings).
        "examples_audio_rate": getattr(_dj_settings, "EXAMPLES_AUDIO_PLAYBACK_RATE", 0.8),
        "examples_pause_seconds": getattr(_dj_settings, "EXAMPLES_PAUSE_SECONDS", 3),
        "step_kind": step_kind,
        "step_index": idx,
        "step_total": len(LESSON_STEP_KINDS),
        "step_kinds": LESSON_STEP_KINDS,
        "prev_kind": prev_kind,
        "next_kind": next_kind,
        "cover_prompt": cover_prompt,
        "image_prompt_for_step": image_prompt_for_step,
        "quiz": quiz,
        "next_lesson": next_lesson,
    })


@login_required
@require_POST
def lesson_tts_clip(request):
    """Return the URL of a NATURAL TTS clip (mp3) for one short lesson item.

    Powers the "listen and repeat" sequencer: each word/example is spoken in a
    natural voice as its own clip, so the player can pause between them.

    Clips are stored as FILES keyed by (voice, text) hash. This is shared across
    gunicorn workers and survives restarts — so each unique item is generated
    ONCE in production (unlike per-process in-memory caching). Failures are NOT
    cached, so a transient TTS hiccup self-heals on the next request (this is
    what caused a one-off "word with no sound").
    """
    import base64
    import hashlib
    import json as _json

    from django.conf import settings as _s
    from django.core.cache import cache
    from django.core.files.base import ContentFile
    from django.core.files.storage import default_storage

    try:
        payload = _json.loads(request.body or "{}")
    except Exception:
        payload = {}
    text = (payload.get("text") or "").strip()
    if not text or len(text) > 240:
        return JsonResponse({"ok": False, "error": "bad_text"}, status=400)

    voice = getattr(_s, "EXAMPLES_TTS_VOICE", None) or getattr(_s, "AI_TTS_VOICE", "alloy")
    digest = hashlib.sha256(f"{voice}|{text}".encode("utf-8")).hexdigest()
    path = f"lesson_tts/{digest}.mp3"

    if not default_storage.exists(path):
        # Light anti-abuse: cap FRESH syntheses per user per hour (existing
        # files are free). Protects the TTS bill from unique-text spam.
        cap = int(getattr(_s, "LESSON_TTS_HOURLY_CAP_PER_USER", 200) or 200)
        gen_key = f"ttsclip_gen:{request.user.id}"
        used = cache.get(gen_key, 0)
        if used >= cap:
            return JsonResponse({"ok": False, "error": "rate_limited"}, status=429)
        cache.set(gen_key, used + 1, 3600)
        try:
            from subscriptions.services import library_audio_service
            res = library_audio_service.synthesize_chunk(text, voice=voice, language="en")
            b64 = res.get("audio_b64") or ""
        except Exception:
            import logging
            logging.getLogger(__name__).exception("lesson_tts_clip synth failed")
            b64 = ""
        if not b64:
            # Do NOT persist failures — retry cleanly next time.
            return JsonResponse({"ok": False, "error": "tts_unavailable"}, status=502)
        try:
            default_storage.save(path, ContentFile(base64.b64decode(b64)))
        except Exception:
            import logging
            logging.getLogger(__name__).exception("lesson_tts_clip save failed")
            return JsonResponse({"ok": False, "error": "tts_unavailable"}, status=502)

    return JsonResponse({"ok": True, "url": default_storage.url(path)})


@login_required
@require_POST
@subscription_required(allow_free_tier=True)
def mark_lesson_complete(request, course_pk, lesson_pk):
    """Mark a courses-app lesson's video as watched.

    Fires the motivation engine inline so XP / streak / achievements
    update without waiting for the nightly cron.
    """
    course = get_object_or_404(published_course_queryset(), pk=course_pk)
    lesson = get_object_or_404(
        published_lesson_queryset().filter(course=course),
        pk=lesson_pk,
    )
    if not can_access_lesson(request.user, lesson):
        return HttpResponseForbidden(_("An active subscription is required for this lesson."))
    drip_redirect = _drip_gate(request, course, lesson)
    if drip_redirect:
        return drip_redirect
    progress, _created = CourseLessonProgress.objects.get_or_create(
        user=request.user, lesson=lesson,
    )
    if not progress.video_completed:
        progress.video_completed = True
        if progress.is_complete and not progress.completed_at:
            progress.completed_at = timezone.now()
        progress.save()
        messages.success(request, _("Marked as watched."))

    try:
        from motivation.services.motivation_engine import run_for_user
        run_for_user(request.user)
    except Exception:
        import logging
        logging.getLogger(__name__).warning(
            "motivation engine post-video failed", exc_info=True
        )

    return redirect("courses:lesson_detail", course_pk=course.pk, lesson_pk=lesson.pk)


@login_required
@require_http_methods(["GET", "POST"])
@subscription_required(allow_free_tier=True)
def lesson_quiz_attempt(request, course_pk, lesson_pk):
    """Sit and grade the lesson's quiz; mirrors lessons.quiz_attempt
    for the courses-app schema."""
    course = get_object_or_404(published_course_queryset(), pk=course_pk)
    lesson = get_object_or_404(
        published_lesson_queryset().filter(course=course),
        pk=lesson_pk,
    )
    if not can_access_lesson(request.user, lesson):
        return HttpResponseForbidden(_("An active subscription is required for this lesson."))
    drip_redirect = _drip_gate(request, course, lesson)
    if drip_redirect:
        return drip_redirect
    try:
        quiz = lesson.quiz
    except Exception:
        raise Http404("Lesson has no quiz")
    if quiz is None or not quiz.is_active:
        raise Http404("Lesson has no active quiz")
    questions = list(quiz.questions.all().order_by("order", "id"))

    if request.method == "GET":
        # Decorate each question with the per-type rendering payload
        # the template needs. Keeping the heavy parsing here keeps
        # the template readable.
        for q in questions:
            md = q.metadata or {}
            # Templates can't access attributes starting with `_`. Use
            # plain names (Django Template language restriction).
            if q.question_type == "sentence_ordering":
                q.scrambled = md.get("words") or list(q.options or [])
            elif q.question_type == "frequency_scale":
                q.scale_items = md.get("scale_items") or []
            elif q.question_type == "table_sentence_builder":
                q.columns = md.get("columns") or {}
                q.min_sentences = int(md.get("min_sentences", 5))
            elif q.question_type == "listening_match":
                q.pairs = md.get("pairs") or []
                q.answer_pool = sorted({p.get("answer", "") for p in q.pairs})
                q.audio_status = md.get("audio_status", "pending_generation")
            elif q.question_type == "speaking_sentence_builder":
                q.speaking_prompt = md.get("student_prompt") or q.question_text
                q.tutor_hint = md.get("ai_tutor_instruction") or ""
            elif q.question_type == "question_transform":
                q.statement = md.get("statement") or ""
                q.target_qword = md.get("target_qword") or ""
        return render(request, "courses/lesson_quiz.html", {
            "course": course,
            "lesson": lesson,
            "quiz": quiz,
            "questions": questions,
        })

    # POST — use the centralised grader so each question_type runs the
    # right rubric (sentence_ordering checks word order, frequency_scale
    # respects tolerance, table_sentence_builder validates 4 columns,
    # etc.).
    from courses.services.quiz_grader import grade_question
    correct_count = 0
    results = []
    for q in questions:
        # Some types submit multiple form fields → collect them all.
        raw = request.POST.get(f"q_{q.id}")
        if raw is None:
            multi = request.POST.getlist(f"q_{q.id}[]")
            raw = multi if multi else ""
        grade = grade_question(q, raw)
        is_correct = bool(grade.get("is_correct"))
        if is_correct:
            correct_count += 1
        chosen = raw if isinstance(raw, str) else " | ".join(raw)
        results.append({
            "q": q, "chosen": chosen,
            "correct": q.correct_answer, "is_correct": is_correct,
            "score": grade.get("score", 0.0),
            "feedback_en": grade.get("feedback_en", ""),
            "feedback_ar": grade.get("feedback_ar", ""),
        })
    total = len(questions) or 1
    score = int(correct_count * 100 / total)
    progress, _created = CourseLessonProgress.objects.get_or_create(
        user=request.user, lesson=lesson,
    )
    progress.quiz_score = score
    progress.quiz_passed = score >= int(quiz.passing_score or 70)
    if progress.is_complete and not progress.completed_at:
        progress.completed_at = timezone.now()
    progress.save()

    if progress.quiz_passed is False:
        _notify_teacher_low_performance(course, request.user, lesson, score)

    personalised_exercises = []
    try:
        from .services.lesson_quiz_adapter import process_course_quiz_submission
        summary = process_course_quiz_submission(request.user, lesson, results)
        personalised_exercises = summary.get("personalised_exercises", [])
    except Exception:
        import logging
        logging.getLogger(__name__).warning(
            "course quiz adapter failed", exc_info=True
        )

    return render(request, "courses/lesson_quiz_result.html", {
        "course": course,
        "lesson": lesson,
        "quiz": quiz,
        "progress": progress,
        "score": score,
        "passed": progress.quiz_passed,
        "results": results,
        "personalised_exercises": personalised_exercises,
    })


# ---------------------------------------------------------------------------
# Game Challenge Engine — Phase 1 (Prompt 02).
# Five small views, each one HTML frame at a time. Legacy quiz views
# above stay untouched.
# ---------------------------------------------------------------------------

def _get_challenge_context(request, course_pk, lesson_pk):
    """Common owner/access checks for every challenge view."""
    course = get_object_or_404(published_course_queryset(), pk=course_pk)
    lesson = get_object_or_404(
        published_lesson_queryset().filter(course=course), pk=lesson_pk,
    )
    if not can_access_lesson(request.user, lesson):
        return None, None, HttpResponseForbidden(
            _("An active subscription is required for this lesson.")
        )
    drip_redirect = _drip_gate(request, course, lesson)
    if drip_redirect:
        return None, None, drip_redirect
    return course, lesson, None


def _get_session_for_user(request, session_id):
    """Fetch a ChallengeSession owned by the requesting user, else 404.

    Hides the session from other users — they get the same 404 instead
    of a 403 (no enumeration of foreign session ids)."""
    from .models import ChallengeSession
    session = get_object_or_404(
        ChallengeSession.objects.filter(user=request.user), pk=session_id,
    )
    return session


@login_required
@subscription_required(allow_free_tier=True)
def challenge_start(request, course_pk, lesson_pk):
    """Create or resume the active session and bounce to its current card."""
    from .services import challenge_runner
    course, lesson, err = _get_challenge_context(request, course_pk, lesson_pk)
    if err:
        return err
    try:
        session = challenge_runner.start_or_resume(request.user, lesson)
    except challenge_runner.ChallengeError as exc:
        messages.error(request, str(exc))
        return redirect("courses:lesson_detail",
                        course_pk=course.pk, lesson_pk=lesson.pk)
    return redirect("courses:challenge_current",
                    course_pk=course.pk, lesson_pk=lesson.pk,
                    session_id=session.pk)


@login_required
@subscription_required(allow_free_tier=True)
def challenge_current(request, course_pk, lesson_pk, session_id):
    """Render the current card (or jump to summary if the session ended)."""
    from .services import challenge_runner
    course, lesson, err = _get_challenge_context(request, course_pk, lesson_pk)
    if err:
        return err
    session = _get_session_for_user(request, session_id)
    if session.lesson_id != lesson.pk:
        raise Http404()

    if session.is_finished:
        return redirect("courses:challenge_summary",
                        course_pk=course.pk, lesson_pk=lesson.pk,
                        session_id=session.pk)

    question = challenge_runner.get_current_question(session)
    if question is None:
        # Walked past the last card without `continue` — finalise.
        challenge_runner.continue_to_next(session)
        return redirect("courses:challenge_summary",
                        course_pk=course.pk, lesson_pk=lesson.pk,
                        session_id=session.pk)

    # If the student has already answered this card (refresh case),
    # render the feedback frame instead of the question frame.
    prior = challenge_runner.has_answered_current(session)

    from .services import question_type_registry as _qtr
    renderer = "courses/question_renderers/" + _qtr.renderer_for(question.question_type)
    spec = _qtr.get_spec(question.question_type) or {}
    kicker = spec.get("label_ar") if (getattr(request, "LANGUAGE_CODE", "") or "").startswith("ar") else spec.get("label_en")

    # Phase 9.5 — ai_roleplay_card.html switches its UI on this flag.
    try:
        from tutor.services import ai_usage_guard
        ai_enabled = ai_usage_guard.is_enabled()
    except Exception:
        ai_enabled = False

    return render(request, "courses/challenge_session.html", {
        "course": course,
        "lesson": lesson,
        "session": session,
        "question": question,
        "question_metadata": question.metadata or {},
        "question_kicker": kicker or question.get_question_type_display(),
        "question_renderer": renderer,
        "is_placeholder_type": bool(spec.get("placeholder")),
        "ai_enabled": ai_enabled,
        "card_number": session.current_question_index + 1,
        "card_total":  session.total_questions,
        "answered":    prior,
    })


@login_required
@require_POST
@subscription_required(allow_free_tier=True)
def challenge_answer(request, course_pk, lesson_pk, session_id):
    """Submit the current card. Re-renders the feedback frame."""
    from .services import challenge_runner
    from .models import LessonQuestion
    course, lesson, err = _get_challenge_context(request, course_pk, lesson_pk)
    if err:
        return err
    session = _get_session_for_user(request, session_id)
    if session.lesson_id != lesson.pk:
        raise Http404()
    if not session.is_active:
        return redirect("courses:challenge_summary",
                        course_pk=course.pk, lesson_pk=lesson.pk,
                        session_id=session.pk)

    question_id = request.POST.get("question_id")
    try:
        question = LessonQuestion.objects.get(pk=int(question_id))
    except (LessonQuestion.DoesNotExist, TypeError, ValueError):
        messages.error(request, _("Invalid question."))
        return redirect("courses:challenge_current",
                        course_pk=course.pk, lesson_pk=lesson.pk,
                        session_id=session.pk)

    raw = request.POST.get("answer")
    if raw is None:
        # Some types submit multi-value form fields under "answer[]".
        multi = request.POST.getlist("answer[]")
        raw = multi if multi else ""
    time_spent = int(request.POST.get("time_spent_seconds") or 0)

    try:
        challenge_runner.submit_answer(
            session, question, raw, time_spent_seconds=time_spent,
        )
    except challenge_runner.ChallengeError:
        # Re-show the current card (likely a refresh that resubmitted).
        pass

    return redirect("courses:challenge_current",
                    course_pk=course.pk, lesson_pk=lesson.pk,
                    session_id=session.pk)


@login_required
@require_POST
@subscription_required(allow_free_tier=True)
def challenge_continue(request, course_pk, lesson_pk, session_id):
    """Advance to the next card. If the session ends, bounce to summary."""
    from .services import challenge_runner
    course, lesson, err = _get_challenge_context(request, course_pk, lesson_pk)
    if err:
        return err
    session = _get_session_for_user(request, session_id)
    if session.lesson_id != lesson.pk:
        raise Http404()
    try:
        challenge_runner.continue_to_next(session)
    except challenge_runner.ChallengeError as exc:
        messages.error(request, str(exc))
    if session.is_finished:
        return redirect("courses:challenge_summary",
                        course_pk=course.pk, lesson_pk=lesson.pk,
                        session_id=session.pk)
    return redirect("courses:challenge_current",
                    course_pk=course.pk, lesson_pk=lesson.pk,
                    session_id=session.pk)


@login_required
@subscription_required(allow_free_tier=True)
def challenge_summary(request, course_pk, lesson_pk, session_id):
    """Render the end-of-Challenge summary screen."""
    course, lesson, err = _get_challenge_context(request, course_pk, lesson_pk)
    if err:
        return err
    session = _get_session_for_user(request, session_id)
    if session.lesson_id != lesson.pk:
        raise Http404()

    next_lesson = (
        published_lesson_queryset()
        .filter(course=course, order__gt=lesson.order)
        .order_by("order")
        .first()
    )
    # Time-spent (best-effort): completed_at - started_at, in whole seconds.
    time_spent_seconds = 0
    if session.completed_at and session.started_at:
        delta = (session.completed_at - session.started_at).total_seconds()
        time_spent_seconds = max(0, int(delta))
    is_perfect = (
        session.status == "completed" and session.wrong_count == 0
    )

    # ---- Phase 5 rewards context ----
    rewards = _build_rewards_context(request, session)
    # ---- Phase 6 learning context ----
    learning = _build_learning_context(session)

    return render(request, "courses/challenge_summary.html", {
        "course": course,
        "lesson": lesson,
        "session": session,
        "next_lesson": next_lesson,
        "time_spent_seconds": time_spent_seconds,
        "is_perfect": is_perfect,
        "rewards": rewards,
        "learning": learning,
    })


# ---------------------------------------------------------------------------
# Phase 7 — AI Tutor inside Challenge endpoints.
# ---------------------------------------------------------------------------

def _get_owned_session(request, session_id, lesson):
    """Return the user's session for `session_id`, scoped to `lesson`.

    404 (not 403) on mismatch — no enumeration of foreign IDs."""
    from .models import ChallengeSession
    session = get_object_or_404(
        ChallengeSession.objects.filter(user=request.user),
        pk=session_id,
    )
    if session.lesson_id != lesson.pk:
        raise Http404()
    return session


@login_required
@require_POST
@subscription_required(allow_free_tier=True)
def ai_explain_wrong_answer(request, course_pk, lesson_pk, session_id, answer_id):
    """Generate (or fetch the rule-based fallback for) an AI explanation
    of a specific WRONG ChallengeAnswer.

    Security:
      * login_required + ownership: session must belong to the user.
      * Answer must belong to that session.
      * No raw prompt accepted — the body has no fields we trust.
      * The view never echoes the student's raw answer back as user input
        to the LLM — it goes through the context builder first.
    """
    from .models import ChallengeAnswer
    from tutor.services import challenge_tutor_service

    course, lesson, err = _get_challenge_context(request, course_pk, lesson_pk)
    if err:
        return err
    session = _get_owned_session(request, session_id, lesson)
    answer = get_object_or_404(
        ChallengeAnswer.objects.filter(session=session), pk=answer_id,
    )

    result = challenge_tutor_service.explain_wrong_answer(request.user, answer)
    return JsonResponse({
        "status": result["status"],
        "reason": result["reason"],
        "explanation_en": result["en"],
        "explanation_ar": result["ar"],
    })


@login_required
@require_POST
@subscription_required(allow_free_tier=True)
def ai_roleplay_start(request, course_pk, lesson_pk, session_id, question_id):
    """Open a short, scoped roleplay session bound to (session, question).

    Returns the roleplay ID + the AI's opening line. If quota is hit or
    AI is off, returns a fallback opener — never a 5xx."""
    from .models import LessonQuestion
    from tutor.services import challenge_tutor_service

    course, lesson, err = _get_challenge_context(request, course_pk, lesson_pk)
    if err:
        return err
    session = _get_owned_session(request, session_id, lesson)
    question = get_object_or_404(
        LessonQuestion.objects.filter(quiz=session.quiz), pk=question_id,
    )
    result = challenge_tutor_service.start_short_roleplay(
        request.user, session, question,
    )
    return JsonResponse({
        "roleplay_id": result["roleplay_id"],
        "opening_en":  result["opening_en"],
        "opening_ar":  result["opening_ar"],
        "status":      result["status"],
        "reason":      result["reason"],
    })


@login_required
@require_POST
@subscription_required(allow_free_tier=True)
def ai_roleplay_message(request, course_pk, lesson_pk, session_id, roleplay_id):
    """Continue an active roleplay. Accepts a short message; refuses
    once `max_turns` is reached."""
    from tutor.models import AIShortRoleplaySession
    from tutor.services import challenge_tutor_service

    course, lesson, err = _get_challenge_context(request, course_pk, lesson_pk)
    if err:
        return err
    session = _get_owned_session(request, session_id, lesson)
    roleplay = get_object_or_404(
        AIShortRoleplaySession.objects.filter(user=request.user),
        pk=roleplay_id,
    )
    if roleplay.challenge_session_id != session.pk:
        raise Http404()

    user_message = (request.POST.get("message") or "").strip()[:500]
    if not user_message:
        return JsonResponse({"status": "failed", "reason": "empty_message"})

    result = challenge_tutor_service.continue_short_roleplay(
        request.user, roleplay, user_message,
    )
    return JsonResponse({
        "reply_en":         result["reply_en"],
        "reply_ar":         result["reply_ar"],
        "status":           result["status"],
        "reason":           result["reason"],
        "turns_remaining":  result["turns_remaining"],
    })


@login_required
@require_POST
@subscription_required(allow_free_tier=True)
def ai_end_advice(request, course_pk, lesson_pk, session_id):
    """One short closing nudge for the Challenge summary. Defaults to
    the rule-based generator if AI is off / over-quota."""
    from tutor.services import challenge_tutor_service

    course, lesson, err = _get_challenge_context(request, course_pk, lesson_pk)
    if err:
        return err
    session = _get_owned_session(request, session_id, lesson)
    result = challenge_tutor_service.generate_end_challenge_advice(
        request.user, session,
    )
    return JsonResponse({
        "advice_en": result["en"],
        "advice_ar": result["ar"],
        "status":    result["status"],
        "reason":    result["reason"],
    })


def _build_learning_context(session) -> dict:
    """Phase-6 learning signal for the Summary view.

    Defensive — every call catches Exception so the Summary still renders
    if `learning_core` is misconfigured.
    """
    out: dict = {}
    try:
        from learning_core.services import mastery_service
        out["skills_practiced"] = mastery_service.skills_practiced_in_session(session)[:5]
    except Exception:
        out["skills_practiced"] = []
    try:
        from learning_core.services import phase6_recommendation
        out["recommendation"] = phase6_recommendation.get_next_best_action(session.user)
        out["weak_skills"]    = phase6_recommendation.get_weak_skills(session.user, limit=3)
    except Exception:
        out["recommendation"] = {}
        out["weak_skills"]    = []
    try:
        from learning_core.services import smart_review_service
        out["due_reviews_count"] = smart_review_service.count_due_now(session.user)
    except Exception:
        out["due_reviews_count"] = 0
    return out


def _build_rewards_context(request, session) -> dict:
    """Pull every Phase-5 reward signal that the Summary template wants.

    Defensive — every call catches Exception so a misconfigured motivation
    app never 500s the Summary page; the student still sees their
    completion with whatever data we have.
    """
    from motivation.services import (
        xp_ledger, streak_v2, daily_goal_service, encouragement_service,
    )
    # XP breakdown by source for this session.
    try:
        breakdown = xp_ledger.xp_breakdown_for_session(session) or {}
    except Exception:
        breakdown = {}
    # Streak state.
    try:
        streak = streak_v2.get_streak(session.user)
    except Exception:
        streak = None
    # Daily goal summary.
    try:
        daily_goal = daily_goal_service.get_daily_goal_summary(session.user)
    except Exception:
        daily_goal = {}
    # Badges newly earned during this session — keyed by session pk via
    # UserBadge.metadata, OR awarded after completion. We surface "earned
    # in the last 5 minutes" so a refresh of /summary shows them.
    try:
        from motivation.models import UserBadge
        recent = list(
            UserBadge.objects.filter(user=session.user)
            .order_by("-earned_at")[:5]
        )
    except Exception:
        recent = []
    # Encouragement message for the page banner.
    try:
        lang = getattr(request, "LANGUAGE_CODE", "en")
        if session.status == "failed":
            event = "challenge_failed"
        elif session.wrong_count == 0 and session.status == "completed":
            event = "perfect_challenge"
        else:
            event = "challenge_completed"
        msg_en, msg_ar = encouragement_service.get_bilingual(
            event, context={"session": session.pk},
        )
    except Exception:
        msg_en, msg_ar = "", ""
    return {
        "xp_breakdown":   breakdown,
        "streak":         streak,
        "daily_goal":     daily_goal,
        "recent_badges":  recent,
        "encouragement_en": msg_en,
        "encouragement_ar": msg_ar,
    }


# ---------------------------------------------------------------------------
# Mistake review (spaced repetition) — recall cards for the student's
# wrong challenge answers. Backend (StudentMistake + smart_review_service)
# is written by the Challenge engine; this is the student-facing review UI.
# ---------------------------------------------------------------------------

@login_required
def mistakes_review(request):
    """Review the student's due mistakes as recall cards (spaced repetition)."""
    from learning_core.services import smart_review_service

    queue = smart_review_service.build_review_queue(request.user, limit=20)
    cards = []
    for item in queue:
        q = item["question"]
        m = item["mistake"]
        cards.append({
            "mistake_id": m.pk,
            "question_en": q.question_text_en or q.question_text,
            "question_ar": q.question_text_ar or q.question_text,
            "correct_answer": m.correct_answer or q.correct_answer,
            "your_answer": m.user_answer or "",
            "explanation_en": m.explanation_en or q.explanation_en or q.explanation,
            "explanation_ar": m.explanation_ar or q.explanation_ar or "",
            "skill": getattr(item.get("skill"), "name", "") or "",
        })
    return render(request, "courses/mistakes_review.html", {
        "cards": cards,
        "total": len(cards),
    })


@login_required
@require_POST
def mistakes_review_record(request, mistake_id):
    """Record a recall result for one mistake and reschedule it."""
    from learning_core.models import StudentMistake
    from learning_core.services import mastery_service, smart_review_service

    mistake = get_object_or_404(StudentMistake, pk=mistake_id, user=request.user)
    correct = request.POST.get("result") == "got_it"
    mastery_service.record_manual_review(mistake, correct=correct)
    return JsonResponse({
        "ok": True,
        "mastered": mistake.mastered,
        "remaining": smart_review_service.count_due_now(request.user),
    })


# ---------------------------------------------------------------------------
# Digital certificates (Marketplace prompt 5)
# ---------------------------------------------------------------------------
from .models import DigitalCertificate  # noqa: E402


@login_required
def certificates_list(request):
    """The student's own issued certificates."""
    certs = (
        DigitalCertificate.objects.filter(student=request.user)
        .select_related("course", "course__level")
    )
    return render(request, "courses/certificates_list.html", {"certificates": certs})


def _cert_student_name(cert):
    """Public-safe display name — the profile full name only, never the
    email/username (these pages are unauthenticated)."""
    return (getattr(getattr(cert.student, "profile", None), "full_name", "") or "").strip()


def certificate_detail(request, cert_uuid):
    """Printable certificate page. Public (shareable by link); the correct
    answer / private data is never shown — only the achievement."""
    cert = get_object_or_404(
        DigitalCertificate.objects.select_related("student", "student__profile", "course", "course__level", "issued_by"),
        certificate_uuid=cert_uuid,
    )
    return render(request, "courses/certificate_detail.html", {"cert": cert, "student_name": _cert_student_name(cert)})


def certificate_verify(request, cert_uuid):
    """Public verification: confirms a certificate UUID is genuine."""
    cert = (
        DigitalCertificate.objects.select_related("student", "student__profile", "course", "course__level")
        .filter(certificate_uuid=cert_uuid)
        .first()
    )
    name = _cert_student_name(cert) if cert else ""
    return render(request, "courses/certificate_verify.html", {"cert": cert, "queried_uuid": cert_uuid, "student_name": name})
