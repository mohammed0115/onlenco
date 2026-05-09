"""Routing constants for the AI engine.

Pipelines are intentionally per-task: a task that can be done by
templates (exercise_generation) gets a longer chain than a task that
only OpenAI can answer well today (writing_feedback).

Confidence thresholds are kept in one place so an operator can tune
them via Django settings without touching code.
"""

# --- Task types -----------------------------------------------------
TASK_ERROR_ANALYSIS        = "error_analysis"
TASK_CEFR_PREDICTION       = "cefr_prediction"
TASK_EXERCISE_GENERATION   = "exercise_generation"
TASK_ANSWER_EXPLANATION    = "answer_explanation"
TASK_TUTOR_REPLY           = "tutor_reply"
TASK_SPEAKING_FEEDBACK     = "speaking_feedback"
TASK_WRITING_FEEDBACK      = "writing_feedback"
TASK_DIFFICULTY_ESTIMATION = "difficulty_estimation"

TASK_TYPE_CHOICES = [
    (TASK_ERROR_ANALYSIS,        "Error analysis"),
    (TASK_CEFR_PREDICTION,       "CEFR prediction"),
    (TASK_EXERCISE_GENERATION,   "Exercise generation"),
    (TASK_ANSWER_EXPLANATION,    "Answer explanation"),
    (TASK_TUTOR_REPLY,           "Tutor reply"),
    (TASK_SPEAKING_FEEDBACK,     "Speaking feedback"),
    (TASK_WRITING_FEEDBACK,      "Writing feedback"),
    (TASK_DIFFICULTY_ESTIMATION, "Difficulty estimation"),
]

# --- Providers -----------------------------------------------------
P_RULES            = "rules"
P_LOCAL_CLASSIFIER = "local_classifier"
P_LOCAL_LLM        = "local_llm"
P_RAG              = "rag"
P_OPENAI           = "openai"
P_NONE             = "none"   # sentinel — no provider succeeded

PROVIDER_CHOICES = [
    (P_RULES,            "Rules"),
    (P_LOCAL_CLASSIFIER, "Local classifier"),
    (P_LOCAL_LLM,        "Local LLM"),
    (P_RAG,              "RAG / question bank"),
    (P_OPENAI,           "OpenAI"),
    (P_NONE,             "None"),
]

# --- Per-task provider pipelines ----------------------------------
# Order matters: each provider is tried in turn; the first one whose
# confidence clears the threshold wins. OpenAI sits at the bottom of
# every chain because it's the most expensive and the least private.
PIPELINES: dict[str, list[str]] = {
    TASK_ERROR_ANALYSIS:      [P_RULES, P_LOCAL_CLASSIFIER, P_LOCAL_LLM, P_OPENAI],
    TASK_CEFR_PREDICTION:     [P_RULES, P_LOCAL_CLASSIFIER, P_LOCAL_LLM, P_OPENAI],
    TASK_EXERCISE_GENERATION: [P_RULES, P_RAG, P_LOCAL_LLM, P_OPENAI],
    TASK_ANSWER_EXPLANATION:  [P_RULES, P_RAG, P_LOCAL_LLM, P_OPENAI],
    TASK_TUTOR_REPLY:         [P_RAG, P_LOCAL_LLM, P_OPENAI],
    TASK_SPEAKING_FEEDBACK:   [P_RULES, P_LOCAL_LLM, P_OPENAI],
    TASK_WRITING_FEEDBACK:    [P_RULES, P_LOCAL_LLM, P_OPENAI],
    # Difficulty regression — local_classifier (TF-IDF + Ridge today,
    # DistilBERT later) is the primary path. No RAG / no LLM fallback —
    # if local can't predict, the rule of "return midpoint with low
    # confidence" is fine because nothing downstream blocks on this.
    TASK_DIFFICULTY_ESTIMATION: [P_RULES, P_LOCAL_CLASSIFIER, P_OPENAI],
}

# --- Confidence thresholds (per provider) -------------------------
# A provider's result is accepted when its self-reported `confidence`
# is at least the threshold; otherwise the router falls through.
DEFAULT_THRESHOLDS: dict[str, float] = {
    P_RULES:            0.90,   # rules either fire confidently or skip
    P_LOCAL_CLASSIFIER: 0.85,
    P_LOCAL_LLM:        0.70,
    P_RAG:              0.70,
    P_OPENAI:           0.50,
}
