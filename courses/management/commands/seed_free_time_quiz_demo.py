"""Seed a demonstration Quiz for Unit 39 (Free Time) using the 6 new
interactive question types of the extended Onlenco Quiz Engine.

All content is original to Onlenco. The 10 recurring students
(Amani, Yusuf, Noor, Kareem, Salma, Omar, Layla, Tarek, Hala, Rashid)
appear across the items; every sentence is original copy authored in
this session for the Onlenco curriculum.

Idempotent — lookups by (quiz, order) so re-running just refreshes the
6 demo questions in place without duplicating.

Target courses: A1 (Elementary) — Unit 39 'Free Time'. The same demo
runs against any other level if `--course-slug` is supplied; the
Onlenco-Beginner A0 course also has a Unit 39 ('Free Time') so it's
included by default.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from courses.models import Course, Lesson, LessonQuestion, LessonQuiz


# ---------------------------------------------------------------------------
# Original Onlenco quiz content — no reuse of any specific source publication.
# Characters: Amani, Yusuf, Noor, Kareem, Salma, Omar, Layla, Tarek, Hala,
# Rashid (defined in ONLENCO_BEGINNER_METHOD_SPEC.md §11).
# ---------------------------------------------------------------------------

QUIZ_TITLE_EN = "Free Time — Adverbs of Frequency"
QUIZ_TITLE_AR = "وقت الفراغ — ظروف التكرار"


def free_time_questions():
    """Return the 6 demo questions, one per interactive type.

    Each entry is a dict shaped for `LessonQuestion.objects.update_or_create`.
    """
    return [
        # 1. Frequency scale — original Onlenco wording, scale positions
        #    follow standard English-pedagogy convention (not from any
        #    specific publication).
        {
            "order": 1,
            "question_type": "frequency_scale",
            "question_text": "Place each word on the scale from 0% (never) to 100% (always).",
            "question_text_en": "Place each word on the scale from 0% (never) to 100% (always).",
            "question_text_ar": "ضع كل كلمة على المقياس من 0٪ (أبداً) إلى 100٪ (دائماً).",
            "options": [],
            "correct_answer": "scale",
            "explanation": "never→0, rarely→15, sometimes→40, often→65, usually→85, always→100 (±10%).",
            "explanation_ar": "never→0، rarely→15، sometimes→40، often→65، usually→85، always→100 (±10٪).",
            "metadata": {
                "scale_items": [
                    {"word": "never",     "percent": 0},
                    {"word": "rarely",    "percent": 15},
                    {"word": "sometimes", "percent": 40},
                    {"word": "often",     "percent": 65},
                    {"word": "usually",   "percent": 85},
                    {"word": "always",    "percent": 100},
                ],
                "tolerance": 10.0,
            },
            "difficulty_score": 0.30,
            "points": 2,
        },

        # 2. Sentence ordering — Onlenco-original sentence about Amani's
        #    free-time routine.
        {
            "order": 2,
            "question_type": "sentence_ordering",
            "question_text": "Put these words in the right order to make a sentence about Amani.",
            "question_text_en": "Put these words in the right order to make a sentence about Amani.",
            "question_text_ar": "رتّب هذه الكلمات لتكوّن جملة عن أماني.",
            "options": ["Amani", "usually", "reads", "novels", "on weekends"],
            "correct_answer": "Amani usually reads novels on weekends",
            "metadata": {
                "words": ["on weekends", "Amani", "novels", "usually", "reads"],
                "correct_order": ["Amani", "usually", "reads", "novels", "on weekends"],
            },
            "difficulty_score": 0.35,
            "points": 2,
        },

        # 3. Table sentence builder — original 4-column matrix using
        #    Onlenco's recurring student cast.
        {
            "order": 3,
            "question_type": "table_sentence_builder",
            "question_text": "Build 4 sentences using one item from each column.",
            "question_text_en": "Build 4 sentences using one item from each column.",
            "question_text_ar": "كوّن 4 جمل باستخدام عنصر من كل عمود.",
            "options": [],
            "correct_answer": "(checked by builder rubric)",
            "metadata": {
                "columns": {
                    "subject":   ["Yusuf", "Noor", "Kareem", "Salma", "I"],
                    "frequency": ["always", "usually", "often", "sometimes", "rarely", "never"],
                    "activity":  ["play soccer", "study English", "cook dinner", "watch movies", "read books"],
                    "time":      ["on Mondays", "after school", "in the evening", "on weekends", "at night"],
                },
                "min_sentences": 4,
            },
            "difficulty_score": 0.45,
            "points": 4,
        },

        # 4. Listening match — original Onlenco transcript; audio file
        #    will be filled by the next TTS batch (status=pending).
        {
            "order": 4,
            "question_type": "listening_match",
            "question_text": "Listen to the audio and match each activity to how often it happens.",
            "question_text_en": "Listen to the audio and match each activity to how often it happens.",
            "question_text_ar": "استمع إلى الصوت وطابق كل نشاط مع تكراره.",
            "options": [],
            "correct_answer": "(pair matching)",
            "metadata": {
                "audio_required": True,
                "audio_status": "pending_generation",
                "audio_script": (
                    "Omar plays basketball every Tuesday and Thursday. "
                    "He almost never misses a game. Layla cooks for her "
                    "family on weekends — never on weekdays. Tarek visits "
                    "his parents once a month."
                ),
                "pairs": [
                    {"activity": "Omar plays basketball",  "answer": "often"},
                    {"activity": "Layla cooks for family", "answer": "sometimes"},
                    {"activity": "Layla cooks on weekdays", "answer": "never"},
                    {"activity": "Tarek visits parents",   "answer": "rarely"},
                ],
            },
            "difficulty_score": 0.40,
            "points": 4,
        },

        # 5. Question transform — statement → How-often question.
        {
            "order": 5,
            "question_type": "question_transform",
            "question_text": "Turn the statement into a How-often question.",
            "question_text_en": "Turn the statement into a How-often question.",
            "question_text_ar": "حوّل الجملة إلى سؤال بـ How often.",
            "options": [],
            "correct_answer": "How often does Hala study English?",
            "explanation": "Use 'How often does' + subject + base verb (no -s).",
            "explanation_ar": "استخدم 'How often does' + الفاعل + الفعل الأساسي (بدون -s).",
            "metadata": {
                "statement": "Hala studies English in the morning.",
                "target_qword": "how often",
            },
            "difficulty_score": 0.45,
            "points": 3,
        },

        # 6. Speaking sentence builder — original Onlenco-style prompt.
        {
            "order": 6,
            "question_type": "speaking_sentence_builder",
            "question_text": "Speak: say 5 sentences about your own free time using adverbs of frequency.",
            "question_text_en": "Speak: say 5 sentences about your own free time using adverbs of frequency.",
            "question_text_ar": "تحدّث: قل 5 جمل عن وقت فراغك مستخدماً ظروف التكرار.",
            "options": [],
            "correct_answer": "(graded by AI tutor)",
            "metadata": {
                "student_prompt": (
                    "Tell the tutor about your own free time. "
                    "Use five different frequency adverbs (always, usually, "
                    "often, sometimes, rarely, never) — one per sentence."
                ),
                "ai_tutor_instruction": (
                    "Listen to the learner. Check (1) word order — frequency "
                    "adverb before the main verb, (2) verb form — base verb "
                    "for I/you/we/they, +s for he/she/it, (3) pronunciation "
                    "of the adverb. Correct gently, one item at a time."
                ),
            },
            "difficulty_score": 0.50,
            "points": 5,
        },
    ]


# Courses that have a Unit 39 "Free Time" lesson. Beginner (A0) calls it
# "Free Time" already; A1 (Elementary) also has it (under cluster 5).
TARGET_COURSES = (
    "onlenco-beginner",     # A0
    "onlenco-elementary",   # A1
)


class Command(BaseCommand):
    help = (
        "Seed a demo Free Time quiz (6 interactive types) into Unit 39 of "
        "each target course. Idempotent."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--course-slug", default=None,
            help=f"Single course slug (default: all in {TARGET_COURSES}).",
        )
        parser.add_argument("--unit", type=int, default=39,
                            help="Lesson order to attach the quiz to (default: 39).")
        parser.add_argument("--quiet", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        slugs = (
            (options["course_slug"],) if options["course_slug"]
            else TARGET_COURSES
        )
        questions = free_time_questions()
        total_q = 0
        for slug in slugs:
            try:
                course = Course.objects.get(slug=slug)
            except Course.DoesNotExist:
                self.stderr.write(self.style.WARNING(
                    f"Course '{slug}' not found — skipped."
                ))
                continue
            lesson = Lesson.objects.filter(
                course=course, order=options["unit"],
            ).first()
            if lesson is None:
                self.stderr.write(self.style.WARNING(
                    f"  {slug}: no lesson at order={options['unit']} — skipped."
                ))
                continue
            quiz, _ = LessonQuiz.objects.update_or_create(
                lesson=lesson,
                defaults={
                    "title":    QUIZ_TITLE_EN,
                    "title_en": QUIZ_TITLE_EN,
                    "title_ar": QUIZ_TITLE_AR,
                    "is_active": True,
                    "passing_score": 70,
                },
            )
            # Drop any older question rows from this quiz so the demo
            # replaces them deterministically.
            LessonQuestion.objects.filter(quiz=quiz).delete()
            for q in questions:
                LessonQuestion.objects.create(quiz=quiz, **q)
                total_q += 1
            if not options["quiet"]:
                self.stdout.write(
                    f"  ✓ {slug} → Unit {options['unit']}: {len(questions)} questions seeded."
                )

        self.stdout.write(self.style.SUCCESS(
            f"Free Time demo quiz seeded — {total_q} questions across {len(slugs)} course(s)."
        ))
