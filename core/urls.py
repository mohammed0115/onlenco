from django.http import JsonResponse
from django.urls import path
from . import views


def healthz(_request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("", views.home, name="home"),
    path("healthz/", healthz, name="healthz"),

    # Public SEO landing pages — indexable, no login wall.
    path("pricing/", views.seo_pricing, name="seo_pricing"),
    path("placement-test/", views.seo_placement_test, name="seo_placement_test"),
    path("ai-english-tutor/", views.seo_ai_english_tutor, name="seo_ai_english_tutor"),
    path("english-for-beginners/", views.seo_english_for_beginners, name="seo_english_for_beginners"),
    path("english-speaking-practice/", views.seo_english_speaking_practice, name="seo_english_speaking_practice"),
]

handler404 = "core.views.not_found"
