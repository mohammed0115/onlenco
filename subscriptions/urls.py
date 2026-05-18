from django.urls import path

from . import views

app_name = "subscriptions"

urlpatterns = [
    path("upgrade/", views.upgrade_page, name="upgrade"),
    path("preferences/", views.preferences_page, name="preferences"),
    path("api/quota/", views.quota_snapshot_api, name="quota_snapshot"),
    path("api/preferences/", views.preference_api, name="preference_api"),
]
