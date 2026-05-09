"""Choices + small policy maps for the question factory."""

# --- Skills (broad axis used across the platform) -----------------------
SKILL_GRAMMAR        = "grammar"
SKILL_VOCABULARY     = "vocabulary"
SKILL_READING        = "reading"
SKILL_LISTENING      = "listening"
SKILL_WRITING        = "writing"
SKILL_SPEAKING       = "speaking"
SKILL_PRONUNCIATION  = "pronunciation"
SKILL_COMPREHENSION  = "comprehension"

SKILL_CHOICES = [
    (SKILL_GRAMMAR,       "Grammar"),
    (SKILL_VOCABULARY,    "Vocabulary"),
    (SKILL_READING,       "Reading"),
    (SKILL_LISTENING,     "Listening"),
    (SKILL_WRITING,       "Writing"),
    (SKILL_SPEAKING,      "Speaking"),
    (SKILL_PRONUNCIATION, "Pronunciation"),
    (SKILL_COMPREHENSION, "Comprehension"),
]

# --- Question types -----------------------------------------------------
QUESTION_TYPE_CHOICES = [
    ("multiple_choice",         "Multiple choice"),
    ("fill_blank",              "Fill in the blank"),
    ("correction",              "Correction"),
    ("sentence_ordering",       "Sentence ordering"),
    ("translation",             "Translation"),
    ("short_answer",            "Short answer"),
    ("reading_comprehension",   "Reading comprehension"),
    ("listening_comprehension", "Listening comprehension"),
    ("speaking_prompt",         "Speaking prompt"),
    ("writing_prompt",          "Writing prompt"),
    ("vocabulary_matching",     "Vocabulary matching"),
    ("grammar_transformation",  "Grammar transformation"),
]

# --- Generation strategy -----------------------------------------------
GEN_TEMPLATE = "template"
GEN_AI       = "ai"
GEN_HYBRID   = "hybrid"
GEN_IMPORTED = "imported"

GEN_STRATEGY_CHOICES = [
    (GEN_TEMPLATE, "Template — deterministic substitution"),
    (GEN_AI,       "AI — LLM-generated end-to-end"),
    (GEN_HYBRID,   "Hybrid — template body + AI explanation/distractors"),
    (GEN_IMPORTED, "Imported — externally curated"),
]

# --- Generation batch status -------------------------------------------
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
