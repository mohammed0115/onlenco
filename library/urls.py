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
]
