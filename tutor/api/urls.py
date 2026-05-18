from django.urls import path

from . import views


urlpatterns = [
    path("chat/send/",        views.chat_send,        name="api_tutor_chat_send"),
    path("chat/stream/",      views.chat_stream,      name="api_tutor_chat_stream"),
    path("voice/transcribe/", views.voice_transcribe, name="api_tutor_voice_transcribe"),
    path("voice/respond/",        views.voice_respond,        name="api_tutor_voice_respond"),
    path("voice/respond/stream/", views.voice_respond_stream, name="api_tutor_voice_respond_stream"),
    path("voice/tts/",        views.voice_tts,        name="api_tutor_voice_tts"),
    path("voice/history/",    views.voice_history,    name="api_tutor_voice_history"),
    path("voice-call/session/",       views.voice_call_session,       name="api_tutor_voice_call_session"),
    path("voice-call/log/",           views.voice_call_log,           name="api_tutor_voice_call_log"),
    path("voice-call/cancel-stale/",  views.voice_call_cancel_stale,  name="api_tutor_voice_call_cancel_stale"),
    path("voice-call/sdp/",           views.voice_call_sdp_relay,     name="api_tutor_voice_call_sdp"),
]
