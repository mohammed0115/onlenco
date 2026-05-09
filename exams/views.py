"""HTML views for the exams app — list, detail, take, result, bank-stats.

The API at exams/api/ serves SPA / mobile clients; these views serve the
template UI for browser users."""
from __future__ import annotations

import json
from collections import Counter

from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Q
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.html import escape
from django.views.decorators.http import require_POST

from learning_core.models import AdaptiveExercise

from . import constants as C
from .models import Exam, ExamAnswer, ExamAttempt, ExamBlueprint, QuestionGenerationBatch
from .services.exam_assembly_service import assemble_exam
from .services.exam_scoring_service import grade_attempt


CEFR_LEVELS = ["A0", "A1", "A2", "B1", "B2", "C1", "C2"]


# ---------------------------------------------------------------------------
# List + landing
# ---------------------------------------------------------------------------

@login_required
def exam_list(request):
    cefr = (request.GET.get("cefr") or "").strip().upper()
    exam_type = (request.GET.get("exam_type") or "").strip()

    blueprints = ExamBlueprint.objects.filter(is_active=True)
    if cefr:
        blueprints = blueprints.filter(cefr_level=cefr)
    if exam_type:
        blueprints = blueprints.filter(exam_type=exam_type)
    blueprints = blueprints.order_by("cefr_level", "exam_type", "skill")

    my_attempts_qs = ExamAttempt.objects.filter(user=request.user)
    my_total = my_attempts_qs.count()
    my_passed = my_attempts_qs.filter(passed=True).count()
    pass_rate = round((my_passed / my_total) * 100) if my_total else 0

    stats = {
        "total_blueprints": ExamBlueprint.objects.filter(is_active=True).count(),
        "total_questions": AdaptiveExercise.objects.filter(is_active=True).count(),
        "my_attempts": my_total,
        "my_pass_rate": pass_rate,
    }

    recent_attempts = (
        my_attempts_qs.select_related("exam").order_by("-started_at")[:5]
    )

    return render(request, "exams/exam_list.html", {
        "blueprints": blueprints,
        "stats": stats,
        "recent_attempts": recent_attempts,
        "cefr": cefr,
        "exam_type": exam_type,
        "cefr_levels": CEFR_LEVELS,
        "exam_types": C.EXAM_TYPE_CHOICES,
    })


@login_required
@require_POST
def exam_assemble(request):
    bp_id = request.POST.get("blueprint_id")
    if not bp_id:
        return HttpResponseBadRequest("blueprint_id required")
    bp = get_object_or_404(ExamBlueprint, pk=bp_id, is_active=True)
    exam = assemble_exam(
        user=request.user,
        blueprint=bp,
        adaptive=bp.exam_type == C.EXAM_REMEDIATION,
    )
    return redirect("exam_detail", pk=exam.pk)


# ---------------------------------------------------------------------------
# Detail
# ---------------------------------------------------------------------------

@login_required
def exam_detail(request, pk: int):
    exam = get_object_or_404(Exam, pk=pk, is_active=True)
    my_attempts_qs = ExamAttempt.objects.filter(user=request.user, exam=exam)
    my_attempts = list(my_attempts_qs.order_by("-started_at")[:10])

    all_attempts = ExamAttempt.objects.filter(exam=exam, status="graded")
    attempts_count = all_attempts.count()
    pass_rate = (
        round(all_attempts.filter(passed=True).count() / attempts_count * 100)
        if attempts_count else 0
    )
    avg = all_attempts.aggregate(a=Avg("percentage")).get("a")
    my_best = my_attempts_qs.order_by("-percentage").first()
    my_best_val = round(my_best.percentage) if my_best else "—"

    stats = {
        "attempts_count": attempts_count,
        "pass_rate": pass_rate,
        "avg_score": round(avg) if avg else 0,
        "my_best": my_best_val,
    }
    return render(request, "exams/exam_detail.html", {
        "exam": exam,
        "blueprint": exam.blueprint,
        "stats": stats,
        "my_attempts": my_attempts,
    })


# ---------------------------------------------------------------------------
# Start + take
# ---------------------------------------------------------------------------

@login_required
@require_POST
def exam_start(request, pk: int):
    exam = get_object_or_404(Exam, pk=pk, is_active=True)
    attempt = ExamAttempt.objects.create(user=request.user, exam=exam)
    return redirect("exam_take", pk=attempt.pk)


@login_required
def exam_take(request, pk: int):
    attempt = get_object_or_404(
        ExamAttempt, pk=pk, user=request.user, status="in_progress",
    )
    exam_questions = list(
        attempt.exam.questions
        .select_related("question", "question__skill", "question__topic")
        .order_by("order")
    )
    payload = []
    for eq in exam_questions:
        q = eq.question
        payload.append({
            "id": q.id,
            "question": q.question or "",
            "options": list(q.options or []),
            "correct_answer": q.correct_answer or "",
            "acceptable_answers": list(q.acceptable_answers or []),
            "explanation": q.explanation or "",
            "question_type": q.question_type,
            "cefr_level": q.cefr_level,
            "skill": q.skill.category if q.skill_id and q.skill else "",
            "topic": q.topic.name if q.topic_id and q.topic else "",
        })
    # Embed safely as JSON inside <script id="exam-data" type="application/json">.
    exam_data = (
        json.dumps(payload, ensure_ascii=False)
        .replace("</", "<\\/")
    )
    return render(request, "exams/take_exam.html", {
        "exam": attempt.exam,
        "attempt": attempt,
        "exam_questions": exam_questions,
        "exam_data": exam_data,
    })


@login_required
@require_POST
def exam_submit(request, pk: int):
    attempt = get_object_or_404(ExamAttempt, pk=pk, user=request.user)
    if attempt.status != "in_progress":
        return redirect("exam_result", pk=attempt.pk)
    answers = []
    for key, val in request.POST.items():
        if not key.startswith("q_"):
            continue
        try:
            qid = int(key.removeprefix("q_"))
        except ValueError:
            continue
        answers.append({"question_id": qid, "user_answer": val})
    grade_attempt(attempt, answers)
    return redirect("exam_result", pk=attempt.pk)


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

@login_required
def exam_result(request, pk: int):
    attempt = get_object_or_404(ExamAttempt, pk=pk, user=request.user)
    answers = list(
        attempt.answers
        .select_related("question", "question__skill")
        .order_by("created_at")
    )
    correct_count = sum(1 for a in answers if a.is_correct)
    skipped_count = sum(1 for a in answers if not (a.user_answer or "").strip())
    wrong_count = len(answers) - correct_count - skipped_count

    duration_str = "—"
    if attempt.submitted_at and attempt.started_at:
        delta = attempt.submitted_at - attempt.started_at
        secs = int(delta.total_seconds())
        m, s = divmod(max(0, secs), 60)
        duration_str = f"{m}:{s:02d}"

    # Per-skill breakdown.
    by_skill: dict[str, dict[str, int]] = {}
    for a in answers:
        sk = (a.question.skill.category if a.question.skill_id and a.question.skill
              else "other")
        bucket = by_skill.setdefault(sk, {"correct": 0, "total": 0})
        bucket["total"] += 1
        if a.is_correct:
            bucket["correct"] += 1
    skill_breakdown = [
        {
            "skill": sk,
            "correct": v["correct"],
            "total": v["total"],
            "pct": round((v["correct"] / v["total"]) * 100) if v["total"] else 0,
        }
        for sk, v in sorted(by_skill.items(), key=lambda kv: -kv[1]["total"])
    ]

    return render(request, "exams/exam_result.html", {
        "attempt": attempt,
        "answers": answers,
        "correct_count": correct_count,
        "wrong_count": wrong_count,
        "skipped_count": skipped_count,
        "total_count": len(answers),
        "duration_str": duration_str,
        "skill_breakdown": skill_breakdown,
    })


# ---------------------------------------------------------------------------
# Bank stats page
# ---------------------------------------------------------------------------

@login_required
def bank_stats(request):
    qs = AdaptiveExercise.objects.all()
    total = qs.count()
    active = qs.filter(is_active=True).count()
    reviewed = qs.filter(is_reviewed=True).count()
    avg_q = qs.aggregate(a=Avg("quality_score")).get("a") or 0.0

    # Group counts (aggregated in DB, not in Python).
    by_cefr = dict(qs.values_list("cefr_level").annotate(c=Count("id")).values_list("cefr_level", "c"))
    by_qtype = dict(qs.values_list("question_type").annotate(c=Count("id")).values_list("question_type", "c"))
    by_gen = dict(qs.values_list("generated_by").annotate(c=Count("id")).values_list("generated_by", "c"))
    by_skill = dict(
        qs.exclude(skill__isnull=True)
          .values_list("skill__category")
          .annotate(c=Count("id"))
          .values_list("skill__category", "c")
    )

    def _shape(d: dict) -> list[tuple[str, dict]]:
        if not d:
            return []
        max_v = max(d.values())
        return sorted(
            ((k or "—", {"count": v, "pct": int((v / max_v) * 100) if max_v else 0})
             for k, v in d.items()),
            key=lambda kv: -kv[1]["count"],
        )

    stats = {
        "total": total,
        "active": active,
        "reviewed": reviewed,
        "avg_quality_score": round(float(avg_q), 1),
        "progress_pct": min(100, round((total / 300_000) * 100)),
    }

    return render(request, "exams/bank_stats.html", {
        "stats": stats,
        "by_cefr_sorted": _shape(by_cefr),
        "by_skill_sorted": _shape(by_skill),
        "by_qtype_sorted": _shape(by_qtype),
        "by_gen_sorted": _shape(by_gen),
        "recent_batches": QuestionGenerationBatch.objects.order_by("-started_at")[:10],
    })
