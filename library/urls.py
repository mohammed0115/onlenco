from django.urls import path

from . import views


urlpatterns = [
    path("", views.book_list, name="library"),
    path("<int:pk>/", views.book_detail, name="library_book"),
]

