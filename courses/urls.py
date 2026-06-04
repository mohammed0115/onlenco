from django.urls import path
from django.views.generic import RedirectView

from . import views


app_name = "courses"

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="library", permanent=False), name="course_index"),
    # Certificates — string prefixes declared before <int:pk> for clarity.
    path("certificates/", views.certificates_list, name="certificates"),
    path("certificate/<uuid:cert_uuid>/", views.certificate_detail, name="certificate_detail"),
    path("verify/<uuid:cert_uuid>/", views.certificate_verify, name="certificate_verify"),
    path("<int:pk>/", views.course_detail, name="course_detail"),
    path("<int:course_pk>/lessons/<int:lesson_pk>/",
         views.course_lesson_detail, name="lesson_detail"),
    path("<int:course_pk>/lessons/<int:lesson_pk>/complete/",
         views.mark_lesson_complete, name="mark_lesson_complete"),
    path("<int:course_pk>/lessons/<int:lesson_pk>/quiz/",
         views.lesson_quiz_attempt, name="lesson_quiz_attempt"),
    # Each lesson "stepper" stage is its own page — deep-linkable,
    # browser-back navigable, and isolated for full immersion.
    path("<int:course_pk>/lessons/<int:lesson_pk>/step/<slug:step_kind>/",
         views.lesson_step, name="lesson_step"),

    # Game Challenge Engine (Phase 1). Each route is one page that
    # renders exactly one card or feedback frame, never the whole
    # quiz at once. Legacy /quiz/ above stays untouched.
    path("<int:course_pk>/lessons/<int:lesson_pk>/challenge/start/",
         views.challenge_start, name="challenge_start"),
    path("<int:course_pk>/lessons/<int:lesson_pk>/challenge/<int:session_id>/current/",
         views.challenge_current, name="challenge_current"),
    path("<int:course_pk>/lessons/<int:lesson_pk>/challenge/<int:session_id>/answer/",
         views.challenge_answer, name="challenge_answer"),
    path("<int:course_pk>/lessons/<int:lesson_pk>/challenge/<int:session_id>/continue/",
         views.challenge_continue, name="challenge_continue"),
    path("<int:course_pk>/lessons/<int:lesson_pk>/challenge/<int:session_id>/summary/",
         views.challenge_summary, name="challenge_summary"),

    # Phase 7 — AI Tutor inside Challenge. Every endpoint is ownership-
    # gated and POST-only — never lets the client pass a raw prompt.
    path("<int:course_pk>/lessons/<int:lesson_pk>/challenge/<int:session_id>/answer/<int:answer_id>/ai-explain/",
         views.ai_explain_wrong_answer, name="ai_explain_wrong_answer"),
    path("<int:course_pk>/lessons/<int:lesson_pk>/challenge/<int:session_id>/roleplay/start/<int:question_id>/",
         views.ai_roleplay_start, name="ai_roleplay_start"),
    path("<int:course_pk>/lessons/<int:lesson_pk>/challenge/<int:session_id>/roleplay/<int:roleplay_id>/message/",
         views.ai_roleplay_message, name="ai_roleplay_message"),
    path("<int:course_pk>/lessons/<int:lesson_pk>/challenge/<int:session_id>/ai-advice/",
         views.ai_end_advice, name="ai_end_advice"),
]
