from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers as drf_serializers
from rest_framework import status
from rest_framework.decorators import action, api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from learning_core.models import (
    AdaptiveExercise,
    ExerciseAttempt,
    LearningRecommendation,
    SkillMastery,
    StudentLearningProfile,
    UserError,
    UserWeakness,
)
from learning_core.services.adaptive_difficulty import (
    get_learning_state,
    process_attempt,
)
from learning_core.services.error_analyzer import analyze_text
from learning_core.services.exercise_generator import generate_personalized_exercises

from .serializers import (
    AdaptiveExerciseSerializer,
    AnalyzeTextInputSerializer,
    ExerciseAttemptInputSerializer,
    ExerciseAttemptSerializer,
    GenerateExercisesInputSerializer,
    LearningRecommendationSerializer,
    SkillMasterySerializer,
    StudentLearningProfileSerializer,
    UserErrorSerializer,
    UserWeaknessSerializer,
)


class LearningProfileView(APIView):
    """Return the authenticated user's adaptive learning profile."""

    permission_classes = [IsAuthenticated]
    serializer_class = StudentLearningProfileSerializer

    @extend_schema(responses=StudentLearningProfileSerializer)
    def get(self, request):
        profile, _ = StudentLearningProfile.objects.get_or_create(user=request.user)
        data = StudentLearningProfileSerializer(profile).data
        data["state"] = get_learning_state(request.user)

        # Behavior signals (engagement / churn / speed)
        try:
            from analytics.services.scoring import (
                churn_risk,
                engagement_score,
                learning_speed_for,
            )
            data["behavior"] = {
                "engagement_score": engagement_score(request.user),
                "churn_risk": churn_risk(request.user),
                "learning_speed": learning_speed_for(request.user),
            }
        except Exception:
            data["behavior"] = {}

        # CEFR progress band — current/next/percent
        try:
            from learning_core.services.adaptive_difficulty import cefr_progress
            data["cefr_progress"] = cefr_progress(profile.theta_score or 0.0)
        except Exception:
            data["cefr_progress"] = {}
        return Response(data)


class SkillMasteryListView(APIView):
    """List per-skill mastery for the current user."""

    permission_classes = [IsAuthenticated]
    serializer_class = SkillMasterySerializer

    @extend_schema(responses=SkillMasterySerializer(many=True))
    def get(self, request):
        qs = (
            SkillMastery.objects.filter(user=request.user)
            .select_related("skill")
            .order_by("-mastery_score")
        )
        return Response(SkillMasterySerializer(qs, many=True).data)


class WeaknessListView(APIView):
    """List active weaknesses for the current user."""

    permission_classes = [IsAuthenticated]
    serializer_class = UserWeaknessSerializer

    @extend_schema(responses=UserWeaknessSerializer(many=True))
    def get(self, request):
        qs = (
            UserWeakness.objects.filter(user=request.user)
            .select_related("skill", "grammar_topic")
            .order_by("-priority_score")[:50]
        )
        return Response(UserWeaknessSerializer(qs, many=True).data)


class UserErrorListView(APIView):
    """List recent UserError rows for the current user."""

    permission_classes = [IsAuthenticated]
    serializer_class = UserErrorSerializer

    @extend_schema(responses=UserErrorSerializer(many=True))
    def get(self, request):
        qs = (
            UserError.objects.filter(user=request.user)
            .select_related("skill", "grammar_topic")
            .order_by("-created_at")[:100]
        )
        return Response(UserErrorSerializer(qs, many=True).data)


class RecommendationListView(APIView):
    """List active LearningRecommendation rows for the current user."""

    permission_classes = [IsAuthenticated]
    serializer_class = LearningRecommendationSerializer

    @extend_schema(responses=LearningRecommendationSerializer(many=True))
    def get(self, request):
        qs = (
            LearningRecommendation.objects.filter(user=request.user)
            .exclude(status="dismissed")
            .order_by("-priority")[:20]
        )
        return Response(LearningRecommendationSerializer(qs, many=True).data)


class GenerateExercisesView(APIView):
    """Generate a fresh batch of personalized exercises for the user."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "ai_exercise_gen"
    serializer_class = GenerateExercisesInputSerializer

    @extend_schema(
        request=GenerateExercisesInputSerializer,
        responses=AdaptiveExerciseSerializer(many=True),
    )
    def post(self, request):
        s = GenerateExercisesInputSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        saved = generate_personalized_exercises(
            request.user, count_per_weakness=s.validated_data["count_per_weakness"]
        )
        return Response(
            AdaptiveExerciseSerializer(saved, many=True).data,
            status=status.HTTP_201_CREATED,
        )


class NextExerciseView(APIView):
    """Return the next exercise the user has not yet attempted."""

    permission_classes = [IsAuthenticated]
    serializer_class = AdaptiveExerciseSerializer

    @extend_schema(responses=AdaptiveExerciseSerializer)
    def get(self, request):
        attempted_ids = list(
            ExerciseAttempt.objects.filter(user=request.user)
            .values_list("exercise_id", flat=True)
        )
        # Level-aware random pick: pull the user's CEFR level off their
        # learning profile, scope the queryset to the band ±1, then random
        # order so consecutive `next/` calls return different items.
        from learning_core.models import StudentLearningProfile
        prof = StudentLearningProfile.objects.filter(user=request.user).first()
        level = (prof.current_cefr_level if prof else "") or "A2"
        levels = ["A0", "A1", "A2", "B1", "B2", "C1", "C2", "C3"]
        i = levels.index(level) if level in levels else 2
        bands = {levels[i]}
        if i > 0:
            bands.add(levels[i - 1])
        if i + 1 < len(levels):
            bands.add(levels[i + 1])
        ex = (
            AdaptiveExercise.objects.exclude(id__in=attempted_ids)
            .filter(cefr_level__in=bands)
            .order_by("?")
            .first()
        )
        if not ex:
            # Last-resort: any unattempted exercise.
            ex = (
                AdaptiveExercise.objects.exclude(id__in=attempted_ids)
                .order_by("?")
                .first()
            )
        if not ex:
            return Response({"detail": "No exercises available."}, status=204)
        return Response(AdaptiveExerciseSerializer(ex).data)


class MicroPracticeView(APIView):
    """Return up to N quick exercises tailored to the user right now."""

    permission_classes = [IsAuthenticated]
    serializer_class = AdaptiveExerciseSerializer

    @extend_schema(responses=AdaptiveExerciseSerializer(many=True))
    def get(self, request):
        from learning_core.services.micro_practice import micro_practice
        try:
            count = max(1, min(int(request.query_params.get("count", "3")), 10))
        except (TypeError, ValueError):
            count = 3
        items = micro_practice(request.user, count=count)
        return Response(AdaptiveExerciseSerializer(items, many=True).data)


class ExerciseAttemptView(APIView):
    """Submit an attempt for an exercise; updates theta + mastery."""

    permission_classes = [IsAuthenticated]
    serializer_class = ExerciseAttemptInputSerializer

    @extend_schema(
        request=ExerciseAttemptInputSerializer,
        responses=ExerciseAttemptSerializer,
    )
    def post(self, request, exercise_id):
        exercise = get_object_or_404(AdaptiveExercise, pk=exercise_id)
        s = ExerciseAttemptInputSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user_answer = s.validated_data["user_answer"].strip()
        is_correct = user_answer.lower() == (exercise.correct_answer or "").strip().lower()
        attempt = ExerciseAttempt.objects.create(
            user=request.user,
            exercise=exercise,
            user_answer=user_answer,
            is_correct=is_correct,
            score=1.0 if is_correct else 0.0,
            time_spent_seconds=s.validated_data["time_spent_seconds"],
        )
        adaptive_result = process_attempt(request.user, exercise, attempt)
        data = ExerciseAttemptSerializer(attempt).data
        data.update(adaptive_result)
        data["correct_answer"] = exercise.correct_answer
        data["explanation"] = exercise.explanation
        return Response(data, status=status.HTTP_201_CREATED)


class AnalyzeTextView(APIView):
    """Run the error analyzer on free-form text."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "ai_analyze_text"
    serializer_class = AnalyzeTextInputSerializer

    @extend_schema(request=AnalyzeTextInputSerializer)
    def post(self, request):
        s = AnalyzeTextInputSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        result = analyze_text(
            request.user,
            s.validated_data["text"],
            source_type=s.validated_data["source_type"],
        )
        return Response(result)


@extend_schema(
    responses=inline_serializer(
        name="HealthResponse",
        fields={
            "status": drf_serializers.CharField(),
            "user": drf_serializers.CharField(),
        },
    )
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def health_check(request):
    return Response({"status": "ok", "user": request.user.username})


class TutorVoiceApiView(APIView):
    """Accept an audio file, transcribe it, send through the tutor chat
    pipeline, and return transcript + reply (and TTS audio if available).

    The optional `conversation_id` and `topic` form fields work like
    `TutorChatApiView`. The audio file is in `audio` (multipart)."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "ai_tutor_chat"
    serializer_class = None

    @extend_schema(
        request={"multipart/form-data": {"type": "object", "properties": {
            "audio": {"type": "string", "format": "binary"},
            "conversation_id": {"type": "integer"},
            "topic": {"type": "string"},
        }}},
        responses=inline_serializer(
            name="TutorVoiceResponse",
            fields={
                "conversation_id": drf_serializers.IntegerField(),
                "transcript": drf_serializers.CharField(),
                "reply": drf_serializers.CharField(),
                "duration_seconds": drf_serializers.IntegerField(),
                "reply_audio_b64": drf_serializers.CharField(allow_blank=True, required=False),
            },
        ),
    )
    def post(self, request):
        from placement.services import transcribe
        from tutor.models import TutorConversation, TutorMessage
        from tutor.services import chat, synthesize

        audio = request.FILES.get("audio")
        if audio is None:
            return Response({"detail": "audio file required"}, status=400)
        if audio.size > 15 * 1024 * 1024:
            return Response({"detail": "audio too large (max 15MB)"}, status=400)
        allowed = {"audio/webm", "audio/ogg", "audio/mpeg", "audio/mp4", "audio/wav", "audio/x-wav"}
        ct = getattr(audio, "content_type", "") or ""
        if ct and ct not in allowed:
            return Response({"detail": f"unsupported content type {ct}"}, status=400)

        stt = transcribe(audio)
        message = stt["transcript"].strip()
        if not message:
            return Response(
                {"detail": "could not transcribe audio (configure AI_API_KEY for live STT)"},
                status=422,
            )

        conv_id = request.POST.get("conversation_id") or request.data.get("conversation_id")
        if conv_id:
            conv = get_object_or_404(TutorConversation, pk=conv_id, user=request.user)
        else:
            topic = request.POST.get("topic") or request.data.get("topic") or ""
            conv = TutorConversation.objects.create(user=request.user, topic=topic)

        TutorMessage.objects.create(conversation=conv, role="user", content=message)
        reply = chat(conv, message)
        TutorMessage.objects.create(conversation=conv, role="assistant", content=reply)
        tts = synthesize(reply)
        return Response(
            {
                "conversation_id": conv.id,
                "transcript": message,
                "reply": reply,
                "duration_seconds": stt["duration_seconds"],
                "reply_audio_b64": tts["audio_b64"],
                "reply_audio_format": tts["format"],
            },
            status=status.HTTP_200_OK,
        )


class TutorChatApiView(APIView):
    """Send a text message to the AI tutor and get a personalised reply."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "ai_tutor_chat"

    @extend_schema(
        request=inline_serializer(
            name="TutorChatRequest",
            fields={
                "conversation_id": drf_serializers.IntegerField(required=False),
                "topic": drf_serializers.CharField(required=False, allow_blank=True),
                "message": drf_serializers.CharField(),
            },
        ),
        responses=inline_serializer(
            name="TutorChatResponse",
            fields={
                "conversation_id": drf_serializers.IntegerField(),
                "reply": drf_serializers.CharField(),
            },
        ),
    )
    def post(self, request):
        from .serializers import TutorChatInputSerializer
        from tutor.models import TutorConversation, TutorMessage
        from tutor.services import chat

        s = TutorChatInputSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        conv_id = s.validated_data.get("conversation_id")
        if conv_id:
            conv = get_object_or_404(TutorConversation, pk=conv_id, user=request.user)
        else:
            conv = TutorConversation.objects.create(
                user=request.user, topic=s.validated_data.get("topic", "")
            )
        message = s.validated_data["message"].strip()
        TutorMessage.objects.create(conversation=conv, role="user", content=message)
        reply = chat(conv, message)
        TutorMessage.objects.create(conversation=conv, role="assistant", content=reply)
        return Response(
            {"conversation_id": conv.id, "reply": reply},
            status=status.HTTP_200_OK,
        )


class PlacementSpeakingUploadApiView(APIView):
    """Accept an audio recording, transcribe via STT, run error analysis,
    and return transcript + scores. Buffered in the session so the next
    call to `/placement/submit/` can attach to PlacementResult."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "ai_placement"
    serializer_class = None

    @extend_schema(
        request={"multipart/form-data": {"type": "object", "properties": {
            "audio": {"type": "string", "format": "binary"},
        }, "required": ["audio"]}},
        responses=inline_serializer(
            name="PlacementSpeakingResponse",
            fields={
                "transcript": drf_serializers.CharField(),
                "duration_seconds": drf_serializers.IntegerField(),
                "fluency_score": drf_serializers.IntegerField(),
                "pronunciation_score": drf_serializers.IntegerField(),
                "stt_confidence": drf_serializers.FloatField(),
                "feedback": drf_serializers.CharField(),
            },
        ),
    )
    def post(self, request):
        from placement.services import fluency_score, pronunciation_score, transcribe
        from learning_core.services.error_analyzer import analyze_text

        audio = request.FILES.get("audio")
        if audio is None:
            return Response({"detail": "audio file required"}, status=400)
        if audio.size > 25 * 1024 * 1024:
            return Response({"detail": "audio too large (max 25MB)"}, status=400)
        allowed = {"audio/webm", "audio/ogg", "audio/mpeg", "audio/mp4", "audio/wav", "audio/x-wav"}
        ct = getattr(audio, "content_type", "") or ""
        if ct and ct not in allowed:
            return Response({"detail": f"unsupported content type {ct}"}, status=400)

        stt = transcribe(audio)
        transcript = stt["transcript"]
        fluency = fluency_score(transcript, stt["duration_seconds"])
        pronunciation = pronunciation_score(transcript, stt["confidence"], fluency)
        if transcript:
            analyze_text(request.user, transcript, source_type="speaking")

        # Buffer in session so /placement/submit/ can attach to PlacementResult
        request.session["pending_speaking"] = {
            "transcript": transcript,
            "duration_seconds": stt["duration_seconds"],
            "fluency_score": fluency,
            "pronunciation_score": pronunciation,
            "stt_confidence": stt["confidence"],
        }
        return Response(
            {
                "transcript": transcript,
                "duration_seconds": stt["duration_seconds"],
                "fluency_score": fluency,
                "pronunciation_score": pronunciation,
                "stt_confidence": stt["confidence"],
                "feedback": (
                    "Live transcription unavailable; please type your spoken answer."
                    if not transcript
                    else "Speaking sample analyzed."
                ),
            },
            status=status.HTTP_200_OK,
        )


class PlacementSubmitApiView(APIView):
    """Submit the full placement test (5 written/spoken answers) and return
    the structured diagnostic + adaptive profile bootstrap."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "ai_placement"
    serializer_class = None

    @extend_schema(
        request=inline_serializer(
            name="PlacementSubmitRequest",
            fields={
                "q1": drf_serializers.CharField(allow_blank=True),
                "q2": drf_serializers.CharField(allow_blank=True),
                "q3": drf_serializers.CharField(allow_blank=True),
                "q4": drf_serializers.CharField(allow_blank=True),
                "q5": drf_serializers.CharField(allow_blank=True),
            },
        ),
    )
    def post(self, request):
        from .serializers import PlacementSubmitInputSerializer
        from placement.models import PlacementResult
        from placement.services import assess
        from placement.services.diagnostic_engine import build_diagnostic_profile

        s = PlacementSubmitInputSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        answers = {k: v for k, v in s.validated_data.items()}

        result = assess(answers)
        pending = request.session.pop("pending_speaking", None) or {}
        placement = PlacementResult.objects.create(
            user=request.user,
            level=result["level"],
            written_score=result.get("written_score"),
            speaking_score=result.get("speaking_score"),
            fluency_score=pending.get("fluency_score") or None,
            pronunciation_score=pending.get("pronunciation_score") or None,
            audio_transcript=pending.get("transcript", "") or "",
            audio_duration_seconds=int(pending.get("duration_seconds") or 0),
            feedback=result.get("feedback", ""),
            transcript=answers,
        )
        profile = request.user.profile
        profile.cefr_level = result["level"]
        profile.placement_completed = True
        profile.save(update_fields=["cefr_level", "placement_completed"])

        diagnostic = build_diagnostic_profile(request.user, answers, assessment=result)
        diagnostic["placement_id"] = placement.id
        diagnostic["audio_transcript"] = placement.audio_transcript
        diagnostic["fluency_score"] = placement.fluency_score
        diagnostic["pronunciation_score"] = placement.pronunciation_score
        return Response(diagnostic, status=status.HTTP_201_CREATED)
