from __future__ import annotations

from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from courses.models import Course
from payments.models import PaymentSubmission
from platform_admin import permissions as perms
from platform_admin.services import course_review_service, dashboard_service, payment_review_service, student_management_service


class IsControlUser(BasePermission):
    def has_permission(self, request, view):
        return perms.is_control_user(request.user)


@extend_schema(exclude=True)
class ControlDashboardAPIView(APIView):
    permission_classes = [IsControlUser]

    def get(self, request):
        metrics = dashboard_service.dashboard_metrics_for(request.user)
        return Response({
            "cards": metrics["cards"],
            "student_summary": metrics["student_summary"],
            "course_summary": metrics["course_summary"],
            "ai_summary": metrics["ai_summary"],
        })


@extend_schema(exclude=True)
class ControlStudentsAPIView(APIView):
    permission_classes = [IsControlUser]

    def get(self, request):
        if not perms.has_capability(request.user, perms.CAP_STUDENTS_VIEW):
            return Response({"detail": "Forbidden"}, status=403)
        qs = student_management_service.student_queryset_for(request.user, request.GET)[:100]
        return Response([
            {
                "id": student.id,
                "email": student.email,
                "name": student_management_service.student_row(student)["name"],
                "level": getattr(student.profile, "cefr_level", None),
                "subscription": getattr(student.profile, "subscription_status", None),
            }
            for student in qs
        ])


@extend_schema(exclude=True)
class ControlStudentDetailAPIView(APIView):
    permission_classes = [IsControlUser]

    def get(self, request, pk):
        User = get_user_model()
        student = get_object_or_404(User.objects.select_related("profile"), pk=pk)
        if not perms.can_view_student(request.user, student):
            return Response({"detail": "Forbidden"}, status=403)
        row = student_management_service.student_row(student)
        return Response({
            "id": student.id,
            "email": student.email,
            "name": row["name"],
            "language": row["language"],
            "level": row["level"],
            "subscription": row["subscription"],
            "risk_status": row["risk_status"],
        })


@extend_schema(exclude=True)
class ControlStudentActionAPIView(APIView):
    permission_classes = [IsControlUser]

    def post(self, request, pk, action):
        User = get_user_model()
        student = get_object_or_404(User, pk=pk)
        if not perms.can_view_student(request.user, student):
            return Response({"detail": "Forbidden"}, status=403)
        if action == "send-notification":
            if not (perms.can_mutate(request.user, perms.CAP_STUDENTS_MANAGE) or perms.has_capability(request.user, perms.CAP_NOTIFICATIONS_MANAGE)):
                return Response({"detail": "Forbidden"}, status=403)
            student_management_service.send_notification(
                request,
                student,
                request.data.get("title") or "Onlenco",
                request.data.get("message") or "",
            )
        elif action == "reset-placement":
            if not perms.can_mutate(request.user, perms.CAP_STUDENTS_MANAGE):
                return Response({"detail": "Forbidden"}, status=403)
            student_management_service.reset_placement(request, student)
        else:
            return Response({"detail": "Unknown action"}, status=404)
        return Response({"ok": True})


@extend_schema(exclude=True)
class ControlPaymentActionAPIView(APIView):
    permission_classes = [IsControlUser]

    def post(self, request, pk, action):
        if not perms.can_manage_payment(request.user):
            return Response({"detail": "Forbidden"}, status=403)
        payment = get_object_or_404(PaymentSubmission, pk=pk)
        if action == "approve":
            payment_review_service.approve_payment(request, payment)
        elif action == "reject":
            reason = (request.data.get("reason") or "").strip()
            if not reason:
                return Response({"reason": "This field is required."}, status=400)
            payment_review_service.reject_payment(request, payment, reason)
        else:
            return Response({"detail": "Unknown action"}, status=404)
        return Response({"ok": True})


@extend_schema(exclude=True)
class ControlCourseActionAPIView(APIView):
    permission_classes = [IsControlUser]

    def post(self, request, pk, action):
        if not perms.can_review_course(request.user):
            return Response({"detail": "Forbidden"}, status=403)
        course = get_object_or_404(Course, pk=pk)
        if action == "approve":
            course_review_service.approve_course(request, course)
        elif action == "reject":
            notes = (request.data.get("notes") or "").strip()
            if not notes:
                return Response({"notes": "This field is required."}, status=400)
            course_review_service.reject_course(request, course, notes)
        else:
            return Response({"detail": "Unknown action"}, status=404)
        return Response({"ok": True})
