"""HTML URL patterns for the exams app."""
from django.urls import path

from . import views

urlpatterns = [
    path("", views.exam_list, name="exam_list"),
    path("bank/", views.bank_stats, name="exam_bank_stats"),
    path("assemble/", views.exam_assemble, name="exam_assemble"),
    path("<int:pk>/", views.exam_detail, name="exam_detail"),
    path("<int:pk>/start/", views.exam_start, name="exam_start"),
    path("attempts/<int:pk>/take/", views.exam_take, name="exam_take"),
    path("attempts/<int:pk>/submit/", views.exam_submit, name="exam_submit"),
    path("attempts/<int:pk>/result/", views.exam_result, name="exam_result"),
]
