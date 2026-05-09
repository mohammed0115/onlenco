from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import generics, serializers as drf_serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from payments.models import (
    PLAN_DETAILS,
    PaymentMethodAccount,
    PaymentSubmission,
)

from .serializers import (
    PaymentMethodAccountSerializer,
    PaymentSubmissionSerializer,
    PlanSerializer,
)


SubscriptionStatusSerializer = inline_serializer(
    name="SubscriptionStatus",
    fields={
        "subscription_status": drf_serializers.CharField(),
        "expires_at": drf_serializers.DateTimeField(allow_null=True),
        "is_subscribed": drf_serializers.BooleanField(),
    },
)


class PaymentPlansView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PlanSerializer

    @extend_schema(responses=PlanSerializer(many=True))
    def get(self, request):
        plans = [
            {"code": code, **details}
            for code, details in PLAN_DETAILS.items()
        ]
        return Response(PlanSerializer(plans, many=True).data)


class PaymentMethodsView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PaymentMethodAccountSerializer
    queryset = PaymentMethodAccount.objects.filter(is_active=True).order_by("sort_order")


class PaymentSubmissionListCreateView(generics.ListCreateAPIView):
    """GET = current user's history. POST = create a new submission."""

    permission_classes = [IsAuthenticated]
    serializer_class = PaymentSubmissionSerializer

    def get_queryset(self):
        return PaymentSubmission.objects.filter(user=self.request.user).order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user, status="pending")


class CurrentSubscriptionView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SubscriptionStatusSerializer

    @extend_schema(responses=SubscriptionStatusSerializer)
    def get(self, request):
        profile = request.user.profile
        return Response({
            "subscription_status": profile.subscription_status,
            "expires_at": profile.subscription_expires_at,
            "is_subscribed": profile.is_subscribed,
        })
