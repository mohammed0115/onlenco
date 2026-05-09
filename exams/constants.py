"""Constants + default policy maps for the exams app."""

# --- Exam types ---
EXAM_PLACEMENT          = "placement"
EXAM_LESSON_QUIZ        = "lesson_quiz"
EXAM_WEEKLY             = "weekly_assessment"
EXAM_MONTHLY            = "monthly_assessment"
EXAM_LEVEL_COMPLETION   = "level_completion"
EXAM_SKILL              = "skill_specific"
EXAM_REMEDIATION        = "weakness_remediation"
EXAM_SPEAKING           = "speaking_assessment"
EXAM_WRITING            = "writing_assessment"
EXAM_VOCABULARY         = "vocabulary_exam"
EXAM_GRAMMAR            = "grammar_exam"

EXAM_TYPE_CHOICES = [
    (EXAM_PLACEMENT,        "Placement exam"),
    (EXAM_LESSON_QUIZ,      "Lesson quiz"),
    (EXAM_WEEKLY,           "Weekly assessment"),
    (EXAM_MONTHLY,          "Monthly assessment"),
    (EXAM_LEVEL_COMPLETION, "Level completion exam"),
    (EXAM_SKILL,            "Skill-specific exam"),
    (EXAM_REMEDIATION,      "Weakness remediation"),
    (EXAM_SPEAKING,         "Speaking assessment"),
    (EXAM_WRITING,          "Writing assessment"),
    (EXAM_VOCABULARY,       "Vocabulary exam"),
    (EXAM_GRAMMAR,          "Grammar exam"),
]

# --- Difficulty labels (paired with the float `difficulty_score`) ---
DIFFICULTY_EASY   = "easy"
DIFFICULTY_MEDIUM = "medium"
DIFFICULTY_HARD   = "hard"
DIFFICULTY_LABEL_CHOICES = [
    (DIFFICULTY_EASY,   "Easy"),
    (DIFFICULTY_MEDIUM, "Medium"),
    (DIFFICULTY_HARD,   "Hard"),
]


def difficulty_label_for(score: float) -> str:
    if score < 0.34:
        return DIFFICULTY_EASY
    if score < 0.67:
        return DIFFICULTY_MEDIUM
    return DIFFICULTY_HARD


# --- Generation batch status ---
BATCH_PENDING   = "pending"
BATCH_RUNNING   = "running"
BATCH_COMPLETED = "completed"
BATCH_FAILED    = "failed"
BATCH_PAUSED    = "paused"

BATCH_STATUS_CHOICES = [
    (BATCH_PENDING,   "Pending"),
    (BATCH_RUNNING,   "Running"),
    (BATCH_COMPLETED, "Completed"),
    (BATCH_FAILED,    "Failed"),
    (BATCH_PAUSED,    "Paused"),
]

# --- Default blueprints (one row per cefr × exam_type) ---
# Tuple: (cefr_level, exam_type, total_questions, duration_minutes,
#         passing_score, question_type_distribution, skill_distribution,
#         difficulty_distribution)
DEFAULT_BLUEPRINTS = [
    # ---- Placement: per-level, mixed
    *[(L, EXAM_PLACEMENT, 20, 25, 60,
       {"multiple_choice": 0.6, "fill_blank": 0.3, "short_answer": 0.1},
       {"grammar": 0.4, "vocabulary": 0.3, "reading": 0.2, "listening": 0.1},
       {"easy": 0.4, "medium": 0.4, "hard": 0.2})
      for L in ("A0", "A1", "A2", "B1", "B2", "C1", "C2")],

    # ---- Weekly assessment: shorter, mixed
    *[(L, EXAM_WEEKLY, 10, 12, 70,
       {"multiple_choice": 0.7, "fill_blank": 0.3},
       {"grammar": 0.5, "vocabulary": 0.5},
       {"easy": 0.3, "medium": 0.5, "hard": 0.2})
      for L in ("A0", "A1", "A2", "B1", "B2", "C1", "C2")],

    # ---- Monthly assessment: longer, harder
    *[(L, EXAM_MONTHLY, 30, 40, 70,
       {"multiple_choice": 0.5, "fill_blank": 0.3, "correction": 0.1, "short_answer": 0.1},
       {"grammar": 0.4, "vocabulary": 0.3, "reading": 0.2, "writing": 0.1},
       {"easy": 0.2, "medium": 0.5, "hard": 0.3})
      for L in ("A0", "A1", "A2", "B1", "B2", "C1", "C2")],

    # ---- Level completion: hardest, used to graduate to the next band
    *[(L, EXAM_LEVEL_COMPLETION, 40, 50, 75,
       {"multiple_choice": 0.4, "fill_blank": 0.3, "correction": 0.15, "short_answer": 0.15},
       {"grammar": 0.35, "vocabulary": 0.25, "reading": 0.2, "listening": 0.1, "writing": 0.1},
       {"easy": 0.1, "medium": 0.5, "hard": 0.4})
      for L in ("A0", "A1", "A2", "B1", "B2", "C1", "C2")],

    # ---- Lesson quiz: small, targeted
    *[(L, EXAM_LESSON_QUIZ, 5, 5, 70,
       {"multiple_choice": 0.8, "fill_blank": 0.2},
       {"grammar": 0.5, "vocabulary": 0.5},
       {"easy": 0.5, "medium": 0.5, "hard": 0.0})
      for L in ("A0", "A1", "A2", "B1", "B2", "C1", "C2")],

    # ---- Skill-specific: grammar / vocabulary / reading / writing / speaking
    *[(L, EXAM_GRAMMAR, 15, 18, 70,
       {"multiple_choice": 0.5, "fill_blank": 0.3, "correction": 0.2},
       {"grammar": 1.0},
       {"easy": 0.3, "medium": 0.4, "hard": 0.3})
      for L in ("A0", "A1", "A2", "B1", "B2", "C1", "C2")],
    *[(L, EXAM_VOCABULARY, 15, 15, 70,
       {"multiple_choice": 0.7, "fill_blank": 0.3},
       {"vocabulary": 1.0},
       {"easy": 0.4, "medium": 0.4, "hard": 0.2})
      for L in ("A0", "A1", "A2", "B1", "B2", "C1", "C2")],

    # ---- Speaking + writing: prompt-driven, fewer items
    *[(L, EXAM_SPEAKING, 3, 10, 60,
       {"speaking_prompt": 1.0},
       {"speaking": 1.0},
       {"easy": 0.2, "medium": 0.6, "hard": 0.2})
      for L in ("A1", "A2", "B1", "B2", "C1", "C2")],
    *[(L, EXAM_WRITING, 3, 25, 60,
       {"writing_prompt": 1.0},
       {"writing": 1.0},
       {"easy": 0.2, "medium": 0.6, "hard": 0.2})
      for L in ("A1", "A2", "B1", "B2", "C1", "C2")],

    # ---- Weakness remediation: fully adaptive at runtime
    *[(L, EXAM_REMEDIATION, 10, 12, 65,
       {"multiple_choice": 0.6, "fill_blank": 0.4},
       {"grammar": 0.6, "vocabulary": 0.4},
       {"easy": 0.5, "medium": 0.4, "hard": 0.1})
      for L in ("A0", "A1", "A2", "B1", "B2", "C1", "C2")],
]
