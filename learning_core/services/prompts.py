"""Prompt templates and JSON schemas for learning_core AI services."""

ERROR_ANALYSIS_SYSTEM = (
    "You are an expert English language teacher and error analyst. "
    "Given a learner's text, identify language errors, classify them, and "
    "produce a corrected version. Be precise, deterministic, and concise. "
    "Categorize errors using these types: grammar, spelling, vocabulary, "
    "punctuation, word_order, pronunciation, comprehension. Skill categories "
    "must be one of: grammar, vocabulary, pronunciation, listening, reading, "
    "writing, speaking. Severity is 1 (trivial) to 10 (blocking). Always "
    "return JSON via the report_errors tool only."
)

ERROR_ANALYSIS_TOOL = {
    "type": "function",
    "function": {
        "name": "report_errors",
        "description": "Return a structured error analysis of the learner text.",
        "parameters": {
            "type": "object",
            "properties": {
                "original_text": {"type": "string"},
                "corrected_text": {"type": "string"},
                "errors": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "error_type": {
                                "type": "string",
                                "enum": [
                                    "grammar",
                                    "spelling",
                                    "vocabulary",
                                    "punctuation",
                                    "word_order",
                                    "pronunciation",
                                    "comprehension",
                                ],
                            },
                            "original_fragment": {"type": "string"},
                            "corrected_fragment": {"type": "string"},
                            "grammar_topic": {"type": "string"},
                            "skill_category": {
                                "type": "string",
                                "enum": [
                                    "grammar",
                                    "vocabulary",
                                    "pronunciation",
                                    "listening",
                                    "reading",
                                    "writing",
                                    "speaking",
                                ],
                            },
                            "severity": {"type": "integer", "minimum": 1, "maximum": 10},
                            "explanation": {"type": "string"},
                            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        },
                        "required": [
                            "error_type",
                            "original_fragment",
                            "corrected_fragment",
                            "severity",
                            "explanation",
                            "confidence",
                        ],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["original_text", "corrected_text", "errors"],
            "additionalProperties": False,
        },
    },
}


EXERCISE_GEN_SYSTEM = (
    "You are an expert English language teacher. Generate concise, "
    "deterministic exercises that match the requested skill, grammar topic, "
    "CEFR level, and difficulty. Return JSON via the produce_exercises tool only."
)

EXERCISE_GEN_TOOL = {
    "type": "function",
    "function": {
        "name": "produce_exercises",
        "description": "Return a batch of exercises.",
        "parameters": {
            "type": "object",
            "properties": {
                "exercises": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "question_type": {
                                "type": "string",
                                "enum": [
                                    "multiple_choice",
                                    "fill_blank",
                                    "correction",
                                    "sentence_building",
                                    "translation",
                                    "short_answer",
                                ],
                            },
                            "question": {"type": "string"},
                            "options": {"type": "array", "items": {"type": "string"}},
                            "correct_answer": {"type": "string"},
                            "explanation": {"type": "string"},
                            "skill": {"type": "string"},
                            "grammar_topic": {"type": "string"},
                            "cefr_level": {
                                "type": "string",
                                "enum": ["A0", "A1", "A2", "B1", "B2", "C1", "C2"],
                            },
                            "difficulty_score": {"type": "number"},
                        },
                        "required": [
                            "question_type",
                            "question",
                            "correct_answer",
                            "explanation",
                            "cefr_level",
                            "difficulty_score",
                        ],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["exercises"],
            "additionalProperties": False,
        },
    },
}


def build_exercise_gen_user_prompt(
    *, skill: str, grammar_topic: str, cefr_level: str, difficulty: float, count: int
) -> str:
    return (
        f"Generate {count} short English exercises.\n"
        f"- Skill: {skill or 'general'}\n"
        f"- Grammar topic: {grammar_topic or 'general'}\n"
        f"- CEFR level: {cefr_level or 'A2'}\n"
        f"- Target difficulty (0-1): {difficulty:.2f}\n"
        "Mix types from: multiple_choice, fill_blank, correction. "
        "Each exercise must be self-contained, unambiguous, and short."
    )


def build_error_analysis_user_prompt(text: str, context: dict | None = None) -> str:
    ctx = ""
    if context:
        cefr = context.get("cefr_level")
        if cefr:
            ctx += f"Learner CEFR level: {cefr}.\n"
        topic = context.get("topic")
        if topic:
            ctx += f"Lesson topic context: {topic}.\n"
    return (
        ctx
        + "Analyze this learner text for language errors and call report_errors:\n"
        + f"---\n{text}\n---"
    )
