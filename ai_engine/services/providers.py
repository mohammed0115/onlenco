"""Provider implementations for the model router.

Each provider is a function with the signature:

    handle(task_type, input_data, context) -> dict | None

Return values:
  * `dict` — `{"output": …, "confidence": float, "model_version": str}`
    when the provider produced a usable result. The router checks the
    confidence against the provider's threshold before accepting it.
  * `None` — the provider chose to skip (no signal, not configured,
    not applicable). The router moves to the next provider.

Design rule: providers must not raise on "I can't help with this" —
they should return None. Real exceptions are reserved for genuine
errors (network down, parse failure) and are logged by the router.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from django.conf import settings

from .. import constants as C

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# rules — cheap deterministic shortcuts
# ---------------------------------------------------------------------------

def rules(task_type: str, input_data: dict, context: dict | None) -> dict | None:
    """Cheap, deterministic shortcuts.

    Each branch returns confidence >= 0.90 only when the rule is
    *certain* — otherwise it skips and the router moves on.
    """
    if task_type == C.TASK_ERROR_ANALYSIS:
        student = (input_data.get("student_answer") or "").strip()
        correct = (input_data.get("correct_answer") or "").strip()
        if student and correct and student.lower() == correct.lower():
            return {
                "output": {
                    "error_type": "none", "correction": correct,
                    "severity": 0,
                    "explanation": "Answer matches the expected answer.",
                },
                "confidence": 0.99, "model_version": "rules-v1",
            }
        if not student:
            return {
                "output": {
                    "error_type": "missing_answer",
                    "correction": correct or "",
                    "severity": 5,
                    "explanation": "No answer was submitted.",
                },
                "confidence": 0.99, "model_version": "rules-v1",
            }
        return None

    if task_type == C.TASK_CEFR_PREDICTION:
        text = (input_data.get("text") or "").strip()
        words = len(text.split())
        # We're confident at the extremes only.
        if words <= 3:
            return {
                "output": {
                    "cefr_level": "A0",
                    "confidence": 0.92,
                    "strengths": [], "weaknesses": ["text_too_short"],
                },
                "confidence": 0.92, "model_version": "rules-v1",
            }
        if words >= 200:
            return {
                "output": {
                    "cefr_level": "C1",
                    "confidence": 0.85,
                    "strengths": ["length"], "weaknesses": [],
                },
                # Borderline — let LLMs improve it.
                "confidence": 0.65, "model_version": "rules-v1",
            }
        return None

    if task_type == C.TASK_EXERCISE_GENERATION:
        # Use the question_factory's deterministic template renderer.
        try:
            from question_factory.models import QuestionBlueprint
            from question_factory.services.template_generator import render_for_blueprint
        except ImportError:
            return None
        cefr = input_data.get("cefr_level") or ""
        skill = input_data.get("skill") or ""
        qs = QuestionBlueprint.objects.filter(is_active=True)
        if cefr:
            qs = qs.filter(cefr_level=cefr)
        if skill:
            qs = qs.filter(skill=skill)
        bp = qs.first()
        if not bp:
            return None
        items = render_for_blueprint(bp, count=1)
        if not items:
            return None
        return {
            "output": items[0],
            "confidence": 0.95,
            "model_version": f"rules-template:{bp.code}",
        }

    if task_type == C.TASK_ANSWER_EXPLANATION:
        # If a stored explanation is supplied via input_data, use it.
        stored = (input_data.get("stored_explanation") or "").strip()
        if stored:
            return {
                "output": {"explanation": stored},
                "confidence": 0.95, "model_version": "rules-v1",
            }
        return None

    if task_type == C.TASK_SPEAKING_FEEDBACK:
        text = (input_data.get("transcript") or "").strip()
        words = len(text.split())
        if words < 5:
            return {
                "output": {
                    "feedback": "Try to speak in longer phrases — at least one full sentence.",
                    "score": max(0, words * 10),
                    "issues": ["too_short"],
                },
                "confidence": 0.92, "model_version": "rules-v1",
            }
        return None

    if task_type == C.TASK_WRITING_FEEDBACK:
        text = (input_data.get("text") or "").strip()
        words = len(text.split())
        if words < 5:
            return {
                "output": {
                    "feedback": "Write at least one complete sentence.",
                    "score": max(0, words * 10),
                    "issues": ["too_short"],
                },
                "confidence": 0.92, "model_version": "rules-v1",
            }
        return None

    return None


# ---------------------------------------------------------------------------
# local_classifier — small models served from the local_models/ registry
# ---------------------------------------------------------------------------

# Lazy-load cache. Keyed by registry path so swapping versions is just a
# settings update + process restart.
_DIFFICULTY_MODEL = None
_CEFR_MODEL = None


def _load_joblib_model(path_setting: str, version_setting: str, cache_var: str):
    """Generic lazy loader for joblib artefacts. Returns dict with
    {pipeline, version, classes} or {pipeline: None} on failure (cached
    so we don't retry every call)."""
    cache = globals().get(cache_var)
    if cache is not None:
        return cache
    path = getattr(settings, path_setting, "")
    if not path:
        globals()[cache_var] = {"pipeline": None}
        return globals()[cache_var]
    try:
        import joblib
        pipeline = joblib.load(path)
        # Extract class labels for classifiers (skip silently for regressors).
        # Direct attribute, then drill into a sklearn Pipeline's last step.
        classes = []
        if hasattr(pipeline, "classes_"):
            classes = list(pipeline.classes_)
        elif hasattr(pipeline, "named_steps"):
            for step in reversed(list(pipeline.named_steps.values())):
                if hasattr(step, "classes_"):
                    classes = list(step.classes_)
                    break
        globals()[cache_var] = {
            "pipeline": pipeline,
            "version": getattr(settings, version_setting, "v0"),
            "classes": classes,
        }
        return globals()[cache_var]
    except Exception as e:
        logger.warning("local_classifier: failed to load %s: %s", path, e)
        globals()[cache_var] = {"pipeline": None}
        return globals()[cache_var]


def _load_difficulty_model():
    return _load_joblib_model(
        "AI_DIFFICULTY_MODEL_PATH",
        "AI_DIFFICULTY_MODEL_VERSION",
        "_DIFFICULTY_MODEL",
    )


def _load_cefr_model():
    return _load_joblib_model(
        "AI_CEFR_MODEL_PATH",
        "AI_CEFR_MODEL_VERSION",
        "_CEFR_MODEL",
    )


def _confidence_from_text_size(text: str) -> float:
    """Tiny heuristic confidence proxy: the model is most reliable on
    items whose length matches the training distribution (questions
    with ~5–25 word stems). Far outside that range we fall to the
    next provider rather than pretending we know.

    Returns a value in [0, 1]."""
    n = len((text or "").split())
    if 4 <= n <= 30:
        return 0.88
    if 2 <= n <= 60:
        return 0.78
    return 0.55


def local_classifier(task_type: str, input_data: dict,
                     context: dict | None) -> dict | None:
    """Local classifier provider.

    Behaviour is per-task:
      * `error_analysis` — heuristic analyzer in learning_core.
      * `difficulty_estimation` — TF-IDF + Ridge regressor trained
        offline (artefact path in `settings.AI_DIFFICULTY_MODEL_PATH`).

    Other tasks return None until a model is wired here.
    """
    if not getattr(settings, "AI_LOCAL_CLASSIFIER_ENABLED", False):
        return None

    # ---- CEFR classification (multi-class) --------------------------
    if task_type == C.TASK_CEFR_PREDICTION:
        model = _load_cefr_model()
        if not model or model.get("pipeline") is None:
            return None
        text = (input_data.get("text") or input_data.get("question") or "").strip()
        if len(text) < 4:
            return None
        try:
            classes = list(model["classes"])
            proba = model["pipeline"].predict_proba([text])[0]
        except Exception as e:
            logger.warning("local_classifier: CEFR predict failed: %s", e)
            return None
        # Argmax + max-probability as confidence. Soft predictions
        # naturally fall through to local_llm/openai when the model
        # isn't sure — exactly what we want given the v0 macro-F1.
        idx = int(proba.argmax())
        confidence = float(proba[idx])
        # Top-3 for debuggability.
        top3 = sorted(
            [(classes[i], float(proba[i])) for i in range(len(classes))],
            key=lambda kv: kv[1], reverse=True,
        )[:3]
        return {
            "output": {
                "cefr_level": classes[idx],
                "confidence": round(confidence, 3),
                "top3": [{"level": l, "p": round(p, 3)} for l, p in top3],
                "strengths": [],
                "weaknesses": [],
            },
            "confidence": confidence,
            "model_version": f"cefr-tfidf-logreg:{model.get('version', 'v0')}",
        }

    # ---- difficulty regression --------------------------------------
    if task_type == C.TASK_DIFFICULTY_ESTIMATION:
        model = _load_difficulty_model()
        if not model or model.get("pipeline") is None:
            return None
        text = (
            input_data.get("text")
            or input_data.get("question")
            or input_data.get("question_text")
            or ""
        ).strip()
        if len(text) < 4:
            return None
        try:
            import numpy as np  # noqa: F401  (sklearn drags numpy)
            yhat = float(model["pipeline"].predict([text])[0])
        except Exception as e:
            logger.warning("local_classifier: difficulty predict failed: %s", e)
            return None
        # Difficulty is bounded [0, 1] by definition.
        yhat = max(0.0, min(1.0, yhat))
        return {
            "output": {
                "label": yhat,
                "difficulty_score": yhat,
            },
            "confidence": _confidence_from_text_size(text),
            "model_version": f"difficulty-tfidf-ridge:{model.get('version', 'v0')}",
        }

    # ---- error analysis (heuristic) --------------------------------
    if task_type == C.TASK_ERROR_ANALYSIS:
        try:
            from learning_core.services.error_analyzer import _heuristic_analyze
        except ImportError:
            return None
        text = (input_data.get("student_answer") or "").strip()
        if not text:
            return None
        result = _heuristic_analyze(text)
        errors = result.get("errors") or []
        if not errors:
            return None
        first = errors[0]
        return {
            "output": {
                "error_type": first.get("error_type") or "grammar",
                "correction": first.get("corrected") or "",
                "severity": int(first.get("severity") or 3),
                "explanation": first.get("explanation") or "",
            },
            "confidence": 0.85,
            "model_version": "heuristic-classifier-v1",
        }

    return None


# ---------------------------------------------------------------------------
# local_llm — local-first generative model
# ---------------------------------------------------------------------------

def _llm_chat(messages: list[dict], *, prefer: str) -> dict | None:
    try:
        from factory.services.llm_router import chat
    except ImportError:
        return None
    return chat(messages, json_mode=True, prefer=prefer)


def _llm_messages_for(task_type: str, input_data: dict) -> list[dict]:
    if task_type == C.TASK_ERROR_ANALYSIS:
        sys = ("You are a strict ESL grammar reviewer. Output JSON: "
               '{"error_type":"...","correction":"...","severity":0..5,'
               '"explanation":"..."}.')
        user = (
            f"Question: {input_data.get('question','')}\n"
            f"Student answer: {input_data.get('student_answer','')}\n"
            f"Correct answer: {input_data.get('correct_answer','')}"
        )
    elif task_type == C.TASK_CEFR_PREDICTION:
        sys = ('You estimate CEFR level from a writing or speaking sample. '
               'Output JSON: {"cefr_level":"A0..C2","confidence":0..1,'
               '"strengths":[...],"weaknesses":[...]}.')
        user = input_data.get("text") or ""
    elif task_type == C.TASK_EXERCISE_GENERATION:
        sys = ('Generate one ESL exercise. Output JSON: {"question":"...",'
               '"options":[...],"correct_answer":"...","explanation":"..."}.')
        user = json.dumps(input_data, ensure_ascii=False)
    elif task_type == C.TASK_ANSWER_EXPLANATION:
        sys = ('Explain in friendly tone why an answer is right or wrong. '
               'Output JSON: {"explanation":"..."}.')
        user = json.dumps({
            "question": input_data.get("question"),
            "student_answer": input_data.get("student_answer"),
            "correct_answer": input_data.get("correct_answer"),
        }, ensure_ascii=False)
    elif task_type == C.TASK_TUTOR_REPLY:
        sys = ('Reply as a patient ESL tutor. Output JSON: {"reply":"..."}.')
        user = json.dumps({
            "student_question": input_data.get("student_question"),
            "context": input_data.get("context") or {},
        }, ensure_ascii=False)
    elif task_type == C.TASK_SPEAKING_FEEDBACK:
        sys = ('Give brief speaking feedback. Output JSON: '
               '{"feedback":"...","score":0..100,"issues":[...]}.')
        user = input_data.get("transcript") or ""
    elif task_type == C.TASK_WRITING_FEEDBACK:
        sys = ('Give brief writing feedback. Output JSON: '
               '{"feedback":"...","score":0..100,"issues":[...]}.')
        user = input_data.get("text") or ""
    else:
        return []
    return [
        {"role": "system", "content": sys},
        {"role": "user",   "content": user},
    ]


def _llm_parse(payload: dict | None) -> dict | None:
    if not payload:
        return None
    try:
        text = payload["choices"][0]["message"].get("content") or ""
        return json.loads(text)
    except Exception:
        return None


def local_llm(task_type: str, input_data: dict,
              context: dict | None) -> dict | None:
    """Local-first LLM provider. Returns None if local endpoint is
    unconfigured or the call fails."""
    if not getattr(settings, "AI_LOCAL_API_BASE", "") or "":
        return None
    messages = _llm_messages_for(task_type, input_data)
    if not messages:
        return None
    payload = _llm_chat(messages, prefer="local")
    if not payload:
        return None
    served_by = (payload.get("_router") or {}).get("served_by")
    if served_by != "local":
        return None  # router fell back to OpenAI — let openai provider handle it
    parsed = _llm_parse(payload)
    if not parsed:
        return None
    model = getattr(settings, "AI_LOCAL_MODEL", "local")
    return {
        "output": parsed,
        "confidence": 0.75,
        "model_version": f"local-llm:{model}",
    }


# ---------------------------------------------------------------------------
# rag — pull from the existing question bank / past replies
# ---------------------------------------------------------------------------

def rag(task_type: str, input_data: dict, context: dict | None) -> dict | None:
    """Lookup an answer in the curated corpus via `retrieval_service`.

    All task-specific retrieval logic lives in the retrieval service —
    this provider is just the adapter that surfaces a single best
    match in the router's expected shape."""
    try:
        from . import retrieval_service
    except ImportError:
        return None

    cefr = input_data.get("cefr_level") or ""
    skill = input_data.get("skill") or ""
    topic = (input_data.get("topic")
             or input_data.get("grammar_topic")
             or input_data.get("vocabulary_topic"))
    difficulty = input_data.get("difficulty")
    qtype = input_data.get("question_type") or ""

    if task_type == C.TASK_EXERCISE_GENERATION:
        bundle = retrieval_service.retrieve_examples(
            task_type, cefr_level=cefr, skill=skill,
            topic=topic, difficulty=difficulty,
            question_type=qtype, limit=1,
        )
        if bundle["count"] == 0:
            return None
        item = bundle["items"][0]
        return {
            "output": {
                "question": item["question"],
                "options": item["options"],
                "correct_answer": item["correct_answer"],
                "explanation": item["explanation"],
                "cefr_level": item["cefr_level"],
                "source_id": item["id"],
            },
            "confidence": 0.85,
            "model_version": f"rag:{item['source']}:{item['id']}",
        }

    if task_type == C.TASK_ANSWER_EXPLANATION:
        bundle = retrieval_service.retrieve_examples(
            task_type, cefr_level=cefr, skill=skill,
            query=(input_data.get("question") or "")[:60], limit=1,
        )
        if bundle["count"] == 0:
            return None
        item = bundle["items"][0]
        explanation = (
            (item.get("output") or {}).get("explanation")
            or item.get("explanation") or ""
        )
        if not explanation:
            return None
        return {
            "output": {"explanation": explanation},
            "confidence": 0.80,
            "model_version": f"rag:{item.get('source','bank')}:{item.get('id','')}",
        }

    if task_type == C.TASK_TUTOR_REPLY:
        bundle = retrieval_service.retrieve_examples(
            task_type, cefr_level=cefr,
            query=(input_data.get("student_question") or "")[:60], limit=1,
        )
        if bundle["count"] == 0:
            return None
        item = bundle["items"][0]
        out = item.get("output") or {}
        reply = out.get("tutor_reply") or out.get("reply") or ""
        if not reply:
            return None
        return {
            "output": {"reply": reply},
            "confidence": 0.75,
            "model_version": f"rag:{item.get('source','tutor')}:{item.get('id','')}",
        }

    return None


# ---------------------------------------------------------------------------
# openai — last resort
# ---------------------------------------------------------------------------

def openai(task_type: str, input_data: dict,
           context: dict | None) -> dict | None:
    """OpenAI-compatible fallback. Returns None when no API key is configured
    so that mis-configured deployments fail closed (caller sees a None
    result and can show a graceful error) rather than crashing."""
    if not getattr(settings, "AI_API_KEY", "") or "":
        return None
    messages = _llm_messages_for(task_type, input_data)
    if not messages:
        return None
    payload = _llm_chat(messages, prefer="openai")
    parsed = _llm_parse(payload)
    if not parsed:
        return None
    model = getattr(settings, "AI_MODEL", "openai")
    return {
        "output": parsed,
        "confidence": 0.85,
        "model_version": f"openai:{model}",
    }


# ---------------------------------------------------------------------------
# Registry — used by the router and by tests for monkey-patching
# ---------------------------------------------------------------------------

PROVIDERS = {
    C.P_RULES:            rules,
    C.P_LOCAL_CLASSIFIER: local_classifier,
    C.P_LOCAL_LLM:        local_llm,
    C.P_RAG:              rag,
    C.P_OPENAI:           openai,
}
