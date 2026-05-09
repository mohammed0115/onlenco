"""Constants for the ai_training app."""

# --- Training task types -------------------------------------------------
TASK_ERROR_ANALYSIS       = "error_analysis"
TASK_CEFR_PREDICTION      = "cefr_prediction"
TASK_EXERCISE_GENERATION  = "exercise_generation"
TASK_ANSWER_EXPLANATION   = "answer_explanation"
TASK_TUTOR_REPLY          = "tutor_reply"

TASK_TYPE_CHOICES = [
    (TASK_ERROR_ANALYSIS,      "Error analysis"),
    (TASK_CEFR_PREDICTION,     "CEFR prediction"),
    (TASK_EXERCISE_GENERATION, "Exercise generation"),
    (TASK_ANSWER_EXPLANATION,  "Answer explanation"),
    (TASK_TUTOR_REPLY,         "Tutor reply"),
]

# --- Dataset build status -----------------------------------------------
BUILD_PENDING   = "pending"
BUILD_RUNNING   = "running"
BUILD_COMPLETED = "completed"
BUILD_FAILED    = "failed"

BUILD_STATUS_CHOICES = [
    (BUILD_PENDING,   "Pending"),
    (BUILD_RUNNING,   "Running"),
    (BUILD_COMPLETED, "Completed"),
    (BUILD_FAILED,    "Failed"),
]

# --- Export format -----------------------------------------------------
FORMAT_JSONL = "jsonl"
FORMAT_CSV   = "csv"

FORMAT_CHOICES = [
    (FORMAT_JSONL, "JSON Lines"),
    (FORMAT_CSV,   "CSV"),
]

# --- Train / val / test split ------------------------------------------
SPLIT_TRAIN      = "train"
SPLIT_VALIDATION = "validation"
SPLIT_TEST       = "test"
SPLIT_ALL        = "all"

SPLIT_CHOICES = [
    (SPLIT_TRAIN,      "Train"),
    (SPLIT_VALIDATION, "Validation"),
    (SPLIT_TEST,       "Test"),
]
