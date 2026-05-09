"""Blueprint CRUD helpers + default seeder."""
from __future__ import annotations

from .. import constants as C
from ..models import ExamBlueprint


def seed_default_blueprints() -> tuple[int, int]:
    """Create one row for every (cefr_level, exam_type, skill) tuple in
    `DEFAULT_BLUEPRINTS`. Idempotent."""
    created = updated = 0
    for row in C.DEFAULT_BLUEPRINTS:
        cefr, etype, total, dur, passing, qtypes, skills, diffs = row
        defaults = {
            "name": f"{cefr} · {dict(C.EXAM_TYPE_CHOICES).get(etype, etype)}",
            "total_questions": total,
            "duration_minutes": dur,
            "passing_score": passing,
            "question_type_distribution": qtypes,
            "skill_distribution": skills,
            "difficulty_distribution": diffs,
            "is_active": True,
        }
        # `skill` column is the dominant skill — taken from the only
        # entry in the skill_distribution if there's exactly one.
        skill = ""
        if isinstance(skills, dict) and len(skills) == 1:
            skill = next(iter(skills))
        obj, created_now = ExamBlueprint.objects.update_or_create(
            cefr_level=cefr, exam_type=etype, skill=skill,
            defaults=defaults,
        )
        if created_now:
            created += 1
        else:
            updated += 1
    return created, updated


def for_signature(*, exam_type: str, cefr_level: str, skill: str = "") -> ExamBlueprint | None:
    return (
        ExamBlueprint.objects
        .filter(exam_type=exam_type, cefr_level=cefr_level, skill=skill, is_active=True)
        .first()
    )
