"""A0 World mission map helpers.

This module turns the existing A0 course lessons into a beginner-friendly
journey. It deliberately does not create a second curriculum source of
truth: lessons remain the playable objects, while missions are the UX layer
that explains the path to an absolute beginner.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from courses.models import Course, Lesson
from courses.services.lesson_gate import annotate_lesson_states


@dataclass(frozen=True)
class A0MissionTemplate:
    slug: str
    title_ar: str
    title_en: str
    instruction_ar: str
    instruction_en: str
    icon: str
    xp_reward: int


A0_BEGINNER_MESSAGE_AR = "أنت تبدأ من الصفر. سنمشي معك خطوة بخطوة."
A0_BEGINNER_MESSAGE_EN = "You are starting from zero. We will go step by step."


A0_MISSION_TEMPLATES: tuple[A0MissionTemplate, ...] = (
    A0MissionTemplate(
        slug="letters_gate",
        title_ar="بوابة الحروف",
        title_en="Letters Gate",
        instruction_ar="اسمع الحرف، شاهده، وقل صوته بهدوء.",
        instruction_en="See the letter, hear it, and say the sound slowly.",
        icon="type",
        xp_reward=20,
    ),
    A0MissionTemplate(
        slug="greetings_city",
        title_ar="مدينة التحيات",
        title_en="Greetings City",
        instruction_ar="تعلم كلمة ترحيب واحدة ورددها بصوتك.",
        instruction_en="Learn one greeting and say it with your voice.",
        icon="message-circle",
        xp_reward=25,
    ),
    A0MissionTemplate(
        slug="my_name_age",
        title_ar="اسمي وعمري",
        title_en="My Name And Age",
        instruction_ar="قل اسمك وعمرك بجملة قصيرة.",
        instruction_en="Say your name and age in one short sentence.",
        icon="user-round",
        xp_reward=25,
    ),
    A0MissionTemplate(
        slug="country_nationality",
        title_ar="رحلة البلد والجنسية",
        title_en="Country Trip",
        instruction_ar="قل من أي بلد أنت بكلمات بسيطة.",
        instruction_en="Say where you are from with simple words.",
        icon="map-pin",
        xp_reward=30,
    ),
    A0MissionTemplate(
        slug="things_around_me",
        title_ar="أشياء حولي",
        title_en="Things Around Me",
        instruction_ar="سم شيئا قريبا منك واسمع نطقه.",
        instruction_en="Name one thing near you and hear it.",
        icon="package",
        xp_reward=30,
    ),
    A0MissionTemplate(
        slug="my_family",
        title_ar="عائلتي",
        title_en="My Family",
        instruction_ar="تعلم كلمة من العائلة واستخدمها في جملة.",
        instruction_en="Learn one family word and use it in a sentence.",
        icon="users-round",
        xp_reward=35,
    ),
    A0MissionTemplate(
        slug="food_drink",
        title_ar="طعام وشراب",
        title_en="Food And Drink",
        instruction_ar="اختر كلمة طعام أو شراب وقل ما تحب.",
        instruction_en="Pick food or drink words and say what you like.",
        icon="utensils",
        xp_reward=35,
    ),
    A0MissionTemplate(
        slug="daily_routine",
        title_ar="روتيني اليومي",
        title_en="My Daily Routine",
        instruction_ar="قل شيئا واحدا تفعله كل يوم.",
        instruction_en="Say one thing you do every day.",
        icon="sun",
        xp_reward=40,
    ),
    A0MissionTemplate(
        slug="first_conversation",
        title_ar="أول محادثة",
        title_en="First Conversation",
        instruction_ar="اجمع ما تعلمته في حوار قصير جدا.",
        instruction_en="Use what you learned in a very short chat.",
        icon="messages-square",
        xp_reward=50,
    ),
)


A0_MICRO_STEPS: tuple[dict[str, str], ...] = (
    {"icon": "text-cursor-input", "label_ar": "كلمة", "label_en": "Word"},
    {"icon": "image", "label_ar": "صورة", "label_en": "Picture"},
    {"icon": "volume-2", "label_ar": "صوت", "label_en": "Sound"},
    {"icon": "message-square", "label_ar": "جملة قصيرة", "label_en": "Short sentence"},
    {"icon": "mic", "label_ar": "تحدث", "label_en": "Speak"},
    {"icon": "circle-help", "label_ar": "سؤال بسيط", "label_en": "Simple question"},
)


def is_a0_course(course: Course | None) -> bool:
    return bool(course and getattr(getattr(course, "level", None), "code", "") == "A0")


def build_a0_world(
    *,
    course: Course,
    lessons: Iterable[Lesson],
    user,
    has_access: bool,
) -> dict:
    """Return the A0 mission-map state for a student and course.

    Unlock state comes from the shared ``annotate_lesson_states`` gate,
    so the A0 mission map and every other course obey the exact same
    sequential daily-drip rule (and the server-side guard agrees).
    """
    lesson_list = list(lessons)
    states = annotate_lesson_states(
        course=course, lessons=lesson_list, user=user, has_access=has_access,
    )

    missions = []
    completed_count = 0
    for index, template in enumerate(A0_MISSION_TEMPLATES):
        row = states[index] if index < len(states) else None
        state = row["state"] if row else "locked"
        if state == "completed":
            completed_count += 1

        missions.append({
            "index": index + 1,
            "slug": template.slug,
            "title_ar": template.title_ar,
            "title_en": template.title_en,
            "instruction_ar": template.instruction_ar,
            "instruction_en": template.instruction_en,
            "icon": template.icon,
            "xp_reward": template.xp_reward,
            "lesson": row["lesson"] if row else None,
            "lesson_url": row["lesson_url"] if row else "",
            "available_on": row["available_on"] if row else None,
            "state": state,
            "is_locked": state == "locked",
            "is_unlocked": state == "unlocked",
            "is_completed": state == "completed",
        })

    return {
        "title_ar": "عالم A0",
        "title_en": "A0 World",
        "message_ar": A0_BEGINNER_MESSAGE_AR,
        "message_en": A0_BEGINNER_MESSAGE_EN,
        "micro_steps": A0_MICRO_STEPS,
        "missions": missions,
        "completed_count": completed_count,
        "total_count": len(A0_MISSION_TEMPLATES),
        "progress_percent": int(round(completed_count / len(A0_MISSION_TEMPLATES) * 100)),
    }
