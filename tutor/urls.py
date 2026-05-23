from django.urls import path

from . import views


urlpatterns = [
    path("", views.conversation_list, name="tutor"),
    path("new/", views.new_conversation, name="tutor_new"),
    path("sanitize/", views.sanitize_for_speech, name="tutor_sanitize"),
    path("voice-call/", views.voice_call_quick, name="tutor_voice_call_quick"),
    path(
        "conversations/delete-mine/",
        views.delete_my_conversations,
        name="tutor_delete_my_conversations",
    ),
    path("<int:pk>/", views.conversation_detail, name="tutor_detail"),
    path("<int:pk>/send/", views.send_message, name="tutor_send"),
    path("<int:pk>/voice-call/", views.voice_call_page, name="tutor_voice_call"),
]

