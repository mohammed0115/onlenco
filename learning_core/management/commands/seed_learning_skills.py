"""Seed the Phase-6 beginner Skill taxonomy.

Each row is upserted by `code`. Re-runnable safely — counts reported.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from learning_core.models import Skill
from learning_core.services.skill_resolver import FALLBACK_SKILL_CODE


# (code, title_en, title_ar, category, cefr_level, sort_order)
BEGINNER_SKILLS = [
    # ---- Greetings + identity ----
    ("greetings",                 "Greetings",                  "تحيات",                "vocabulary", "A0",  10),
    ("alphabet",                  "Alphabet",                   "الحروف الأبجدية",     "pronunciation", "A0", 20),
    ("spelling_names",            "Spelling names",             "تهجئة الأسماء",       "vocabulary", "A0",  30),
    ("to_be_names",               "Be: names",                  "be: الأسماء",         "grammar",    "A0",  40),
    ("to_be_age",                 "Be: age",                    "be: العمر",           "grammar",    "A0",  50),
    ("nationality",               "Nationality",                "الجنسية",             "vocabulary", "A0",  60),
    ("numbers_basic",             "Numbers (basic)",            "الأرقام الأساسية",    "vocabulary", "A0",  70),

    # ---- Family + home ----
    ("family_words",              "Family words",               "كلمات العائلة",       "vocabulary", "A0",  80),
    ("pets_animals",              "Pets & animals",             "حيوانات أليفة",       "vocabulary", "A0",  90),
    ("possessive_adjectives",     "Possessive adjectives",      "صفات الملكية",        "grammar",    "A1", 100),
    ("this_that",                 "This / That",                "هذا / ذلك",          "grammar",    "A1", 110),
    ("these_those",               "These / Those",              "هؤلاء / أولئك",       "grammar",    "A1", 120),
    ("apostrophe_s",              "Apostrophe 's",              "علامة الملكية 's",    "grammar",    "A1", 130),
    ("everyday_objects",          "Everyday objects",           "أغراض يومية",         "vocabulary", "A0", 140),

    # ---- Work + time ----
    ("jobs",                      "Jobs",                       "المهن",               "vocabulary", "A1", 150),
    ("workplaces",                "Workplaces",                 "أماكن العمل",         "vocabulary", "A1", 160),
    ("telling_time",              "Telling time",               "قول الوقت",           "grammar",    "A1", 170),
    ("daily_routine",             "Daily routine",              "الروتين اليومي",      "vocabulary", "A1", 180),

    # ---- Present simple ----
    ("present_simple",            "Present simple",             "المضارع البسيط",      "grammar",    "A1", 190),
    ("third_person_s",            "Third-person 's'",           "صيغة الغائب",         "grammar",    "A1", 200),
    ("negatives_to_be",           "Negatives with 'be'",        "نفي be",              "grammar",    "A1", 210),
    ("present_simple_negative",   "Present simple negative",    "المضارع البسيط (نفي)","grammar",    "A1", 220),
    ("yes_no_questions",          "Yes/No questions",           "أسئلة نعم/لا",        "grammar",    "A1", 230),
    ("short_answers",             "Short answers",              "إجابات قصيرة",        "grammar",    "A1", 240),
    ("question_words",            "Question words (Wh-)",       "أدوات الاستفهام",     "grammar",    "A1", 250),

    # ---- Quantifiers + articles ----
    ("there_is_are",              "There is / are",             "There is / are",      "grammar",    "A1", 260),
    ("articles_a_an_the",         "Articles a/an/the",          "أدوات التعريف والتنكير","grammar",  "A1", 270),

    # ---- Places + directions ----
    ("directions",                "Directions",                 "الاتجاهات",           "vocabulary", "A1", 280),
    ("conjunctions_and_but",      "And / But",                  "and / but",           "grammar",    "A1", 290),
    ("adjectives_basic",          "Adjectives (basic)",         "الصفات الأساسية",     "grammar",    "A1", 300),
    ("because_reasons",           "Because / reasons",          "because (السبب)",     "grammar",    "A1", 310),

    # ---- Food + shopping ----
    ("have_has",                  "Have / has",                 "have / has",          "grammar",    "A1", 320),
    ("food_drink",                "Food & drink",               "الطعام والشراب",      "vocabulary", "A1", 330),
    ("countable_uncountable",     "Countable / uncountable",    "العد / غير العد",     "grammar",    "A1", 340),
    ("how_much_many",             "How much / many",            "How much / many",     "grammar",    "A1", 350),
    ("clothes",                   "Clothes",                    "الملابس",             "vocabulary", "A1", 360),
    ("shopping",                  "Shopping",                   "التسوّق",             "vocabulary", "A1", 370),

    # ---- Free time ----
    ("sports",                    "Sports",                     "الرياضات",            "vocabulary", "A1", 380),
    ("hobbies",                   "Hobbies",                    "الهوايات",            "vocabulary", "A1", 390),
    ("adverbs_frequency",         "Adverbs of frequency",       "ظروف التكرار",        "grammar",    "A1", 400),
    ("likes_dislikes",            "Likes / dislikes",           "أحب / لا أحب",       "grammar",    "A1", 410),
    ("favorite",                  "Favorite",                   "المفضّل",             "vocabulary", "A1", 420),
    ("can_cannot",                "Can / can't",                "can / can't",        "grammar",    "A1", 430),
    ("adverbs_manner",            "Adverbs of manner",          "ظروف الكيفية",        "grammar",    "A2", 440),
    ("good_at_bad_at",            "Good at / Bad at",           "بارع في / ضعيف في",   "grammar",    "A1", 450),
    ("would_like_want",           "Would like / want",          "أودّ / أريد",         "grammar",    "A2", 460),
    ("studying_subjects",         "Studying subjects",          "المواد الدراسية",     "vocabulary", "A1", 470),

    # ---- Skills (placeholders) ----
    ("listening_basic",           "Listening — basic",          "استماع — أساسي",     "listening",  "A0", 480),
    ("speaking_intro",            "Speaking — introduction",    "محادثة — تمهيد",     "speaking",   "A0", 490),
    ("pronunciation_basic",       "Pronunciation — basic",      "نطق — أساسي",        "pronunciation","A0", 500),

    # ---- Prompt 12B.1 additions ----
    # NOTE: `error_correction` is a LearningSkill code for error/correction
    # practice. It is deliberately NOT named `mistake_correction` to avoid a
    # namespace clash with the `mistake_correction` *question_type* (a separate
    # model/field; the distinct name prevents confusion).
    ("error_correction",          "Error correction",           "تصحيح الأخطاء",       "grammar",    "A1", 475),
    ("places_in_town",            "Places in town",             "أماكن في المدينة",    "vocabulary", "A1", 155),

    # ---- Fallback ----
    (FALLBACK_SKILL_CODE,         "General beginner skill",     "مهارة عامة للمبتدئ", "vocabulary", "A0", 9999),
]


class Command(BaseCommand):
    help = "Seed/refresh the Phase-6 beginner skill taxonomy."

    def handle(self, *args, **options):
        created, updated = 0, 0
        for code, title_en, title_ar, category, cefr, sort in BEGINNER_SKILLS:
            obj, was_new = Skill.objects.update_or_create(
                code=code,
                defaults={
                    "name":           title_en,
                    "title_en":       title_en,
                    "title_ar":       title_ar,
                    "category":       category,
                    "cefr_level":     cefr,
                    "sort_order":     sort,
                    "is_active":      True,
                    "description":    "",
                    "description_ar": "",
                },
            )
            created += int(was_new)
            updated += int(not was_new)
        self.stdout.write(self.style.SUCCESS(
            f"[OK] Learning skills seeded: {created} created, "
            f"{updated} updated, {len(BEGINNER_SKILLS)} total."
        ))
