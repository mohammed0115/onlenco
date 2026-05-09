from django.db.models import Avg, Count
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import generics, serializers as drf_serializers, status
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from learning_core.models import AdaptiveExercise

from ..models import Exam, ExamAttempt, ExamBlueprint
from ..services.exam_assembly_service import assemble_exam
from ..services.exam_scoring_service import grade_attempt

from .serializers import (
    AssembleRequestSerializer,
    ExamAttemptSerializer,
    ExamBlueprintSerializer,
    ExamSerializer,
    QuestionBankStatsSerializer,
    SubmitAnswersSerializer,
)


class ExamBlueprintListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ExamBlueprintSerializer
    queryset = ExamBlueprint.objects.filter(is_active=True)


class AssembleExamView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AssembleRequestSerializer

    @extend_schema(request=AssembleRequestSerializer, responses=ExamSerializer)
    def post(self, request):
        s = AssembleRequestSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            exam = assemble_exam(
                user=request.user,
                exam_type=s.validated_data["exam_type"],
                cefr_level=s.validated_data["cefr_level"],
                skill=s.validated_data.get("skill", ""),
                adaptive=s.validated_data.get("adaptive", False),
            )
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(ExamSerializer(exam).data, status=status.HTTP_201_CREATED)


class ExamDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ExamSerializer
    queryset = Exam.objects.filter(is_active=True)


class StartExamAttemptView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ExamAttemptSerializer

    @extend_schema(request=None, responses=ExamAttemptSerializer)
    def post(self, request, pk):
        exam = get_object_or_404(Exam, pk=pk, is_active=True)
        attempt = ExamAttempt.objects.create(user=request.user, exam=exam)
        return Response(ExamAttemptSerializer(attempt).data, status=status.HTTP_201_CREATED)


class SubmitExamAttemptView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SubmitAnswersSerializer

    @extend_schema(request=SubmitAnswersSerializer, responses=ExamAttemptSerializer)
    def post(self, request, pk):
        attempt = get_object_or_404(ExamAttempt, pk=pk, user=request.user)
        s = SubmitAnswersSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        attempt = grade_attempt(attempt, s.validated_data["answers"])
        return Response(ExamAttemptSerializer(attempt).data)


class MyAttemptsView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ExamAttemptSerializer

    def get_queryset(self):
        return ExamAttempt.objects.filter(user=self.request.user).order_by("-started_at")


class QuestionBankStatsView(APIView):
    """Bank-wide stats. Public (read-only, aggregate)."""
    permission_classes = [IsAuthenticated]
    serializer_class = QuestionBankStatsSerializer

    @extend_schema(responses=QuestionBankStatsSerializer)
    def get(self, request):
        qs = AdaptiveExercise.objects.all()
        total = qs.count()
        active = qs.filter(is_active=True).count()
        reviewed = qs.filter(is_reviewed=True).count()
        avg_q = qs.aggregate(a=Avg("quality_score")).get("a") or 0.0

        # Group counts in the database, not by streaming every row into a
        # Python Counter. At 300k+ items the Counter approach would scan
        # the whole table; GROUP BY uses the existing indexes.
        def _group(field: str, qs_=qs) -> dict:
            return {
                (k or ""): v for k, v in
                qs_.values_list(field).annotate(c=Count("id"))
                   .values_list(field, "c")
            }

        data = {
            "total": total, "active": active, "reviewed": reviewed,
            "by_cefr": _group("cefr_level"),
            "by_skill": _group("skill__category", qs.exclude(skill__isnull=True)),
            "by_question_type": _group("question_type"),
            "by_generated_by": _group("generated_by"),
            "avg_quality_score": round(float(avg_q), 1),
        }
        return Response(data)
