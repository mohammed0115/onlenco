from django.urls import path

from . import views


urlpatterns = [
    path("", views.book_list, name="library"),
    path("<int:pk>/", views.book_detail, name="library_book"),
    path(
        "chapters/<int:chapter_id>/position/",
        views.update_position,
        name="library_update_position",
    ),
    path(
        "chapters/<int:chapter_id>/complete/",
        views.mark_chapter_complete,
        name="library_chapter_complete",
    ),
    path(
        "chapters/<int:chapter_id>/comprehension/",
        views.submit_comprehension,
        name="library_submit_comprehension",
    ),
    path(
        "chapters/<int:chapter_id>/summary/",
        views.chapter_summary,
        name="library_chapter_summary",
    ),
    path(
        "chapters/<int:chapter_id>/reader/",
        views.chapter_reader,
        name="library_chapter_reader",
    ),
    path(
        "chapters/<int:chapter_id>/listen/",
        views.chapter_listen,
        name="library_chapter_listen",
    ),
    path(
        "chapters/<int:chapter_id>/audio/stream/",
        views.chapter_audio_stream,
        name="library_audio_stream",
    ),
    path(
        "chapters/<int:chapter_id>/audio/start/",
        views.chapter_audio_start,
        name="library_audio_start",
    ),
    path(
        "chapters/<int:chapter_id>/audio/chunk/",
        views.chapter_audio_chunk,
        name="library_audio_chunk",
    ),
    path(
        "chapters/<int:chapter_id>/audio/finish/",
        views.chapter_audio_finish,
        name="library_audio_finish",
    ),
]
