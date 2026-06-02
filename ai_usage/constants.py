"""Shared choice vocabularies for the ai_usage app.

Centralised so services, models, admin, and API all speak the same codes.
"""
from __future__ import annotations

# --- provider -----------------------------------------------------------
PROVIDER_OPENAI = "openai"
PROVIDER_OTHER = "other"
PROVIDER_CHOICES = [
    (PROVIDER_OPENAI, "OpenAI"),
    (PROVIDER_OTHER, "Other"),
]

# --- role ---------------------------------------------------------------
ROLE_STUDENT = "student"
ROLE_TEACHER = "teacher"
ROLE_ADMIN = "admin"
ROLE_SYSTEM = "system"
ROLE_CHOICES = [
    (ROLE_STUDENT, "Student"),
    (ROLE_TEACHER, "Teacher"),
    (ROLE_ADMIN, "Admin"),
    (ROLE_SYSTEM, "System"),
]

# --- feature ------------------------------------------------------------
FEATURE_PLACEMENT_WRITTEN = "placement_written"
FEATURE_PLACEMENT_SPEAKING = "placement_speaking"
FEATURE_AI_TUTOR = "ai_tutor"
FEATURE_LESSON_ASSISTANT = "lesson_assistant"
FEATURE_VOCABULARY = "vocabulary"
FEATURE_LIBRARY = "library"
FEATURE_MOTIVATION = "motivation"
FEATURE_CONTENT_GENERATION = "content_generation"
FEATURE_CHALLENGE_EXPLANATION = "challenge_explanation"
FEATURE_CHALLENGE_ROLEPLAY = "challenge_roleplay"
FEATURE_CHALLENGE_END_ADVICE = "challenge_end_advice"
FEATURE_READING_LISTENING = "reading_listening"
FEATURE_STT = "stt"
FEATURE_TTS = "tts"
FEATURE_MEDIA_GENERATION = "media_generation"
FEATURE_OTHER = "other"
FEATURE_CHOICES = [
    (FEATURE_PLACEMENT_WRITTEN, "Placement (written)"),
    (FEATURE_PLACEMENT_SPEAKING, "Placement (speaking)"),
    (FEATURE_AI_TUTOR, "AI Tutor"),
    (FEATURE_LESSON_ASSISTANT, "Lesson assistant"),
    (FEATURE_VOCABULARY, "Vocabulary"),
    (FEATURE_LIBRARY, "Library"),
    (FEATURE_MOTIVATION, "Motivation"),
    (FEATURE_CONTENT_GENERATION, "Content generation"),
    (FEATURE_CHALLENGE_EXPLANATION, "Challenge explanation"),
    (FEATURE_CHALLENGE_ROLEPLAY, "Challenge roleplay"),
    (FEATURE_CHALLENGE_END_ADVICE, "Challenge end advice"),
    (FEATURE_READING_LISTENING, "Reading/listening assistant"),
    (FEATURE_STT, "Speech-to-text"),
    (FEATURE_TTS, "Text-to-speech"),
    (FEATURE_MEDIA_GENERATION, "Media generation"),
    (FEATURE_OTHER, "Other"),
]

# Features whose usage is a live student speaking session and therefore
# consumes the daily AI-Tutor minute allowance.
MINUTE_BEARING_FEATURES = {FEATURE_AI_TUTOR}

# --- status -------------------------------------------------------------
STATUS_SUCCESS = "success"
STATUS_FAILED = "failed"
STATUS_CANCELLED = "cancelled"
STATUS_CHOICES = [
    (STATUS_SUCCESS, "Success"),
    (STATUS_FAILED, "Failed"),
    (STATUS_CANCELLED, "Cancelled"),
]
