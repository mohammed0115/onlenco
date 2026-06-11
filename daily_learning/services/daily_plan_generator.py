"""Orchestrator — turns a (user, date) into a DailyLearningPlan.

Sourcing order (cheapest first):
  1. If level is A0  → fixed A0 topic (hand-curated, never AI).
  2. Otherwise:
     a. Build review-mistake items from learning_core.UserError (up to 2).
     b. Try AdaptiveExercise question bank for quiz / writing / reading.
     c. Try DictionaryEntry for vocabulary.
     d. Top up missing slots from level_templates.TopicTemplate items.
     e. If still short and AI is allowed under the daily cap → call
        ai_engine.model_router and merge validated AI items.

The result is always a DailyLearningPlan with 5–8 items + a DailyGoal
+ a motivation_message stored in metadata. Idempotent on (user, date).
"""
from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from ..models import (
    DailyLearningItem,
    DailyLearningPlan,
)
from . import (
    a0_templates,
    ai_prompts,
    daily_challenge_service,
    daily_content_selector,
    daily_goal_service,
    daily_message_generator,
    daily_review_service,
    level_templates,
)

logger = logging.getLogger(__name__)


# Public entry --------------------------------------------------------

def generate_for_user(user, *, on_date: _date | None = None, force: bool = False,
                       allow_ai: bool | None = None) -> DailyLearningPlan:
    """Generate (or fetch) today's plan for `user`.

    Re-running with the same (user, on_date) is a no-op unless
    `force=True`, in which case the existing plan is deleted and
    regenerated.

    `allow_ai` overrides settings — None means "use the project setting".
    """
    on_date = on_date or timezone.localdate()
    ai_enabled = (settings.DAILY_LEARNING_USE_AI if allow_ai is None else allow_ai)

    profile = _safe_profile(user)
    learning_profile = _safe_learning_profile(user)
    language = (getattr(profile, "preferred_language", "en") or "en")
    cefr_level = _resolve_cefr(profile, learning_profile)
    plan_type = daily_challenge_service.decide_plan_type(
        user, on_date, profile, learning_profile
    )

    # Idempotent — return the existing plan if it already exists AND
    # matches the current spec. Regenerate when:
    #   * the level changed (Profile was corrected after generation),
    #   * the item shape drifted (e.g. a 7- or 8-item plan from a prior
    #     template version still hangs around — the spec is now 6 items
    #     for A0). Without this, learners would see stale legacy shapes
    #     until midnight or until an operator wiped the row by hand.
    existing = DailyLearningPlan.objects.filter(user=user, date=on_date).first()
    if existing and not force:
        level_matches = (existing.cefr_level or "") == cefr_level
        shape_matches = _existing_shape_matches_current_spec(existing, cefr_level)
        if level_matches and shape_matches:
            return existing
        existing.delete()
    elif existing and force:
        existing.delete()

    if cefr_level == "A0":
        plan = _generate_a0_plan(
            user=user,
            on_date=on_date,
            language=language,
            plan_type=plan_type,
        )
    else:
        plan = _generate_leveled_plan(
            user=user,
            on_date=on_date,
            cefr_level=cefr_level,
            language=language,
            plan_type=plan_type,
            ai_enabled=ai_enabled,
            profile=profile,
        )

    # Day goal (separate row, not part of the plan items)
    try:
        daily_goal_service.ensure_daily_goal(user, on_date, cefr_level)
        daily_goal_service.ensure_streak_goal(user, on_date)
    except Exception:
        logger.exception("ensure_daily_goal failed for user=%s date=%s", user.id, on_date)

    return plan


# ---- A0 path --------------------------------------------------------

def _generate_a0_plan(*, user, on_date, language, plan_type) -> DailyLearningPlan:
    """Emit one A0 lesson (exactly 6 items) for today.

    A0 lessons are hand-curated in `a0_templates` and already carry
    their own encouragement closer — we do NOT append an extra
    motivation item here, which would push the plan to 7 items and
    break the spec's 6-item shape.
    """
    topic = a0_templates.pick_next_topic_for_user(user, on_date=on_date)
    closing_item = topic.items[-1] if topic.items else None
    motivation = (
        (closing_item.content_text_ar if language == "ar" else closing_item.content_text_en)
        if closing_item and closing_item.item_type == "motivation"
        else daily_message_generator.motivation_message(
            cefr_level="A0", language=language, on_date=on_date,
            user_id=user.id, plan_type=plan_type,
        )
    )
    title = topic.title_ar if language == "ar" else topic.title_en
    description = topic.description_ar if language == "ar" else topic.description_en

    with transaction.atomic():
        plan = DailyLearningPlan.objects.create(
            user=user,
            date=on_date,
            cefr_level="A0",
            plan_type=plan_type if plan_type in {
                "beginner_start", "streak_recovery", "normal_daily_plan"
            } else "beginner_start",
            title=title,
            description=description,
            estimated_minutes=10,
            metadata={
                "language": language,
                "topic_slug": topic.slug,
                "topic_unit": topic.unit,
                "motivation_message": motivation,
                "source": "a0_template",
            },
        )
        for order, src in enumerate(topic.items):
            DailyLearningItem.objects.create(
                daily_plan=plan,
                item_type=src.item_type,
                title=src.title_ar if language == "ar" else src.title_en,
                instructions=src.instructions_ar if language == "ar" else src.instructions_en,
                content_text=(src.content_text_ar if language == "ar" else src.content_text_en),
                question=(src.question_ar if language == "ar" else src.question_en),
                options=list(src.options_ar if language == "ar" else src.options),
                correct_answer=src.correct_answer,
                explanation=(src.explanation_ar if language == "ar" else src.explanation_en),
                image_url=src.image_url,
                audio_url=src.audio_url,
                cefr_level="A0",
                skill=src.skill,
                difficulty_score=0.1,
                order=order,
                estimated_minutes=src.estimated_minutes,
                metadata={"source": "a0_template", "topic": topic.slug, "unit": topic.unit},
            )
    return plan


# ---- leveled (A1+) path --------------------------------------------

def _generate_leveled_plan(
    *, user, on_date, cefr_level, language, plan_type, ai_enabled, profile,
) -> DailyLearningPlan:
    min_items, max_items = daily_challenge_service.item_count_for_plan_type(
        plan_type,
        min_items=settings.DAILY_LEARNING_MIN_ITEMS,
        max_items=settings.DAILY_LEARNING_MAX_ITEMS,
        comeback_items=settings.DAILY_LEARNING_COMEBACK_ITEMS,
    )
    # 1. Review-mistake items (skip for streak_recovery so the comeback
    #    plan stays gentle).
    review_items: list[dict] = []
    if plan_type != "streak_recovery":
        review_items = daily_review_service.build_review_items(
            user, limit=2, language=language
        )

    # 2. Question-bank items.
    bank_items: list[dict] = []
    used_exercise_ids: list[int] = []
    for slot_skill in _slot_skills_for(plan_type):
        item = daily_content_selector.pick_question_from_bank(
            user=user,
            cefr_level=cefr_level,
            skill=slot_skill,
            exclude_ids=used_exercise_ids,
        )
        if item:
            bank_items.append(item)
            ex_id = (item.get("metadata") or {}).get("exercise_id")
            if ex_id:
                used_exercise_ids.append(ex_id)
        if len(bank_items) >= 3:
            break

    # 3. Vocabulary slot from dictionary
    vocab_items: list[dict] = []
    vocab = daily_content_selector.pick_vocabulary_item(
        user=user, cefr_level=cefr_level, language=language,
    )
    if vocab:
        vocab_items.append(vocab)

    collected = review_items + vocab_items + bank_items

    # 4. Pull a level template for any still-missing slots.
    template_items: list[dict] = []
    template_topic = level_templates.pick_topic_for_level(
        cefr_level, on_date.toordinal(), user.id
    )
    if template_topic:
        for src in template_topic.items:
            template_items.append({
                "item_type": src.item_type,
                "title": src.title_ar if language == "ar" else src.title_en,
                "instructions": src.instructions_ar if language == "ar" else src.instructions_en,
                "content_text": src.content_text,
                "question": src.question,
                "options": list(src.options),
                "correct_answer": src.correct_answer,
                "explanation": src.explanation_ar if language == "ar" else src.explanation_en,
                "cefr_level": cefr_level,
                "skill": src.skill,
                "difficulty_score": src.difficulty_score,
                "estimated_minutes": src.estimated_minutes,
                "metadata": {"source": "level_template", "topic": template_topic.slug},
            })

    # Compose items in a balanced order: vocab → grammar → reading →
    # speaking/writing → quiz → review. Cap at max_items.
    composed = _compose_items(
        review_items=review_items,
        vocab_items=vocab_items,
        bank_items=bank_items,
        template_items=template_items,
        max_items=max_items,
    )

    # 5. AI fallback — only if we're still short AND AI is allowed AND
    #    the per-user daily cap hasn't been hit.
    if len(composed) < min_items and ai_enabled and _ai_under_cap(user, on_date):
        ai_items, ai_meta = _maybe_ai_generate(
            user=user,
            cefr_level=cefr_level,
            language=language,
            plan_type=plan_type,
            estimated_minutes=15,
        )
        if ai_items:
            # Take only as many as needed to reach min_items.
            need = max(0, min_items - len(composed))
            composed.extend(ai_items[:need])

    composed = composed[:max_items]
    # Guarantee at least one quiz and one speaking item if we have room.
    composed = _ensure_required_skills(composed, template_items, max_items)

    motivation = daily_message_generator.motivation_message(
        cefr_level=cefr_level, language=language, on_date=on_date,
        user_id=user.id, plan_type=plan_type,
    )

    title, description = _plan_title_description(
        plan_type=plan_type,
        cefr_level=cefr_level,
        language=language,
        template_topic=template_topic,
    )

    # Optional listen_build_sentence item (Prompt 18.3B) — opt-in via setting so
    # existing plan shapes/tests are unaffected by default. Appended only when
    # there is a free slot, so the 5..max shape stays valid (non-A0 only).
    if getattr(settings, "DAILY_LISTEN_BUILD_ENABLED", False):
        has_lb = any((c.get("metadata") or {}).get("listen_build") for c in composed)
        if not has_lb and len(composed) < max_items:
            from . import daily_listen_build
            composed.append(daily_listen_build.build_listen_build_item(
                cefr_level=cefr_level, language=language,
                seed=on_date.toordinal() if on_date else 0,
            ))

    with transaction.atomic():
        plan = DailyLearningPlan.objects.create(
            user=user,
            date=on_date,
            cefr_level=cefr_level,
            plan_type=plan_type,
            title=title,
            description=description,
            estimated_minutes=sum(i.get("estimated_minutes", 2) for i in composed) + 1,
            metadata={
                "language": language,
                "motivation_message": motivation,
                "min_items": min_items,
                "max_items": max_items,
            },
        )
        for order, src in enumerate(composed):
            DailyLearningItem.objects.create(
                daily_plan=plan,
                item_type=src["item_type"],
                title=src.get("title", ""),
                instructions=src.get("instructions", ""),
                content_text=src.get("content_text", ""),
                question=src.get("question", ""),
                options=list(src.get("options") or []),
                correct_answer=src.get("correct_answer", ""),
                explanation=src.get("explanation", ""),
                cefr_level=src.get("cefr_level", cefr_level),
                skill=src.get("skill", "mixed"),
                difficulty_score=float(src.get("difficulty_score", 0.3)),
                order=order,
                estimated_minutes=int(src.get("estimated_minutes", 2)),
                metadata=src.get("metadata", {}),
            )
        # Motivation item as the closer.
        DailyLearningItem.objects.create(
            daily_plan=plan,
            item_type="motivation",
            title=("رسالة تحفيز" if language == "ar" else "A word of encouragement"),
            instructions="",
            content_text=motivation,
            cefr_level=cefr_level,
            skill="mixed",
            difficulty_score=0.0,
            order=len(composed),
            estimated_minutes=1,
            metadata={"source": "motivation"},
        )
    return plan


# ---- composition helpers -------------------------------------------

def _slot_skills_for(plan_type: str) -> list[str]:
    """Which skills should we try to pull from the bank?"""
    if plan_type == "weakness_review":
        return ["grammar", "vocabulary", "writing"]
    if plan_type == "exam_preparation":
        return ["grammar", "reading", "vocabulary"]
    return ["vocabulary", "grammar", "reading"]


def _compose_items(*, review_items, vocab_items, bank_items, template_items, max_items):
    """Interleave sources into a sensible order, dedupe by skill+content."""
    composed: list[dict] = []
    seen_signatures: set[str] = set()

    def _push(item: dict) -> bool:
        sig = (item["item_type"], (item.get("question") or item.get("content_text") or item.get("title") or "")[:60])
        if sig in seen_signatures:
            return False
        seen_signatures.add(sig)
        composed.append(item)
        return True

    # Vocab first (warm-up)
    for it in vocab_items:
        if len(composed) >= max_items:
            return composed
        _push(it)
    # Then template grammar tip / reading
    for it in template_items:
        if len(composed) >= max_items:
            return composed
        if it["item_type"] in {"grammar_tip", "reading"}:
            _push(it)
    # Bank items (quiz / writing)
    for it in bank_items:
        if len(composed) >= max_items:
            return composed
        _push(it)
    # Template speaking / writing / quiz next
    for it in template_items:
        if len(composed) >= max_items:
            return composed
        if it["item_type"] in {"speaking", "writing", "quiz"}:
            _push(it)
    # Reviews at the end so the warm-up isn't blocked by mistakes
    for it in review_items:
        if len(composed) >= max_items:
            return composed
        _push(it)
    # Any remaining template items
    for it in template_items:
        if len(composed) >= max_items:
            return composed
        _push(it)
    return composed


def _ensure_required_skills(composed, template_items, max_items):
    """Guarantee at least one speaking item and at least one quiz item."""
    have_speaking = any(i["item_type"] in {"speaking", "ai_tutor_practice"} for i in composed)
    have_quiz = any(i["item_type"] == "quiz" for i in composed)
    if have_speaking and have_quiz:
        return composed
    for src in template_items:
        if len(composed) >= max_items:
            break
        if not have_speaking and src["item_type"] == "speaking":
            composed.append(src)
            have_speaking = True
        elif not have_quiz and src["item_type"] == "quiz":
            composed.append(src)
            have_quiz = True
        if have_speaking and have_quiz:
            break
    return composed


# ---- AI fallback -----------------------------------------------------

def _ai_under_cap(user, on_date) -> bool:
    """Return True when this user has not yet hit today's AI cap."""
    cap = getattr(settings, "DAILY_LEARNING_AI_DAILY_CAP_PER_USER", 1)
    if cap <= 0:
        return False
    today_plans = DailyLearningPlan.objects.filter(
        user=user, date=on_date,
    )
    used = 0
    for p in today_plans:
        used += int((p.metadata or {}).get("ai_calls_used", 0))
    return used < cap


def _maybe_ai_generate(*, user, cefr_level, language, plan_type, estimated_minutes
                       ) -> tuple[list[dict], dict]:
    """Call the AI router and return validated items.

    Returns ([], {}) on any failure — the orchestrator just falls
    back to template items in that case.
    """
    try:
        from ai_engine.services.model_router import route_task
        from ai_engine import constants as Ac
    except Exception:
        return [], {}

    prompt = ai_prompts.build_prompt(
        cefr_level=cefr_level,
        language=language,
        weaknesses=daily_review_service.get_top_weaknesses(user, limit=3),
        mistakes=daily_review_service.get_recent_mistakes(user, limit=3),
        onboarding_path=getattr(getattr(user, "profile", None), "onboarding_path", "") or "",
        estimated_minutes=estimated_minutes,
        plan_type=plan_type,
    )

    try:
        result = route_task(
            Ac.TASK_EXERCISE_GENERATION,
            input_data={"prompt": prompt, "format": "daily_plan_json"},
            user=user,
            context={"cefr_level": cefr_level, "language": language},
        )
    except Exception:
        logger.exception("ai_engine route_task raised")
        return [], {}

    if result.get("provider") == "none":
        return [], {}
    output = result.get("output") or {}
    cleaned = ai_prompts.validate_ai_output(output)
    if not cleaned:
        return [], {}
    items = []
    for raw_item in cleaned["items"]:
        raw_item["cefr_level"] = cefr_level
        raw_item.setdefault("estimated_minutes", 2)
        raw_item.setdefault("metadata", {})
        raw_item["metadata"]["source"] = "ai"
        items.append(raw_item)
    return items, {
        "title": cleaned["title"],
        "description": cleaned["description"],
        "motivation_message": cleaned["motivation_message"],
    }


# ---- profile lookups (defensive) -----------------------------------

def _existing_shape_matches_current_spec(existing, cefr_level: str) -> bool:
    """Detect plans created by an older template version so they get
    regenerated instead of served stale.

    Today's spec:
      * A0  → exactly 6 items, no `writing` and no `word_order`.
      * other levels → 5..max_items range, anything is fine.

    Anything outside those guards is treated as a legacy plan and the
    generator regenerates from scratch.
    """
    try:
        items = list(existing.items.all())
    except Exception:
        return True   # be permissive on any read error — never block
    if cefr_level == "A0":
        if len(items) != 6:
            return False
        types = {i.item_type for i in items}
        if "writing" in types or "word_order" in types:
            return False
    return True


def _safe_profile(user):
    try:
        return user.profile
    except Exception:
        return None


def _safe_learning_profile(user):
    try:
        from learning_core.models import StudentLearningProfile
        return StudentLearningProfile.objects.filter(user=user).first()
    except Exception:
        return None


def _resolve_cefr(profile, learning_profile) -> str:
    """Decide which CEFR level the daily plan should be tuned to.

    `Profile.cefr_level` is the source of truth — it is set deliberately
    (onboarding choice, placement result, A0→A1 promotion service) and
    represents what the platform officially considers the learner's
    level. `learning_profile.current_cefr_level` mirrors theta and can
    drift; relying on it would generate an A2 plan for an A0 learner
    whose theta crept up, which is exactly the bug Scenario B was
    reporting in the audit."""
    if profile and getattr(profile, "cefr_level", None):
        return profile.cefr_level
    if learning_profile and getattr(learning_profile, "current_cefr_level", ""):
        return learning_profile.current_cefr_level
    return "A1"


def _plan_title_description(*, plan_type, cefr_level, language, template_topic):
    if plan_type == "streak_recovery":
        if language == "ar":
            return ("خطة عودة قصيرة", "درس قصير لإعادتك إلى مسارك.")
        return ("A short comeback plan", "One short lesson to restart your streak.")
    if plan_type == "weakness_review":
        if language == "ar":
            return ("راجع نقاطك الضعيفة", "تمارين قصيرة موجّهة لنقاطك التي تحتاج إلى تدريب.")
        return ("Review your weak spots", "Short, targeted practice on areas you need.")
    if template_topic:
        return (
            template_topic.title_ar if language == "ar" else template_topic.title_en,
            template_topic.description_ar if language == "ar" else template_topic.description_en,
        )
    if language == "ar":
        return (f"خطة اليوم — {cefr_level}", "خطة تعلم قصيرة لليوم.")
    return (f"Today's plan — {cefr_level}", "A short learning plan for today.")
