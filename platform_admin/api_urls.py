from django.urls import path

from . import api


app_name = "platform_admin_api"

urlpatterns = [
    path("dashboard/", api.ControlDashboardAPIView.as_view(), name="dashboard"),
    path("students/", api.ControlStudentsAPIView.as_view(), name="students"),
    path("students/<int:pk>/", api.ControlStudentDetailAPIView.as_view(), name="student_detail"),
    path("students/<int:pk>/<slug:action>/", api.ControlStudentActionAPIView.as_view(), name="student_action"),
    path("payments/<int:pk>/<slug:action>/", api.ControlPaymentActionAPIView.as_view(), name="payment_action"),
    path("courses/<int:pk>/<slug:action>/", api.ControlCourseActionAPIView.as_view(), name="course_action"),
]
