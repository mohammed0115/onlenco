"""Verify placement feedback rendered to the user is humanized — no raw
snake_case identifiers, JSON blobs, or unresolved templates leak through."""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from placement.models import PlacementResult

User = get_user_model()


@override_settings(AXES_ENABLED=False)
class PlacementFeedbackHumanizationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="pl@x.com", email="pl@x.com", password="pw"
        )
        prof = self.user.profile
        prof.cefr_level = "B1"
        prof.placement_completed = True
        # Pin English so we can compare against the EN glossary deterministically.
        prof.preferred_language = "en"
        prof.save()
        # Feedback contains technical tokens that must NOT reach the page.
        PlacementResult.objects.create(
            user=self.user,
            level="B1",
            written_score=70,
            speaking_score=65,
            feedback="Your theta_score improved. Watch your weakness_detected events.",
        )
        self.client.login(username="pl@x.com", password="pw")

    def test_already_taken_renders_humanized_feedback(self):
        # Force English locale so the EN glossary applies inside the
        # template's `{{ ...|humanize }}` filter.
        resp = self.client.get(reverse("placement"), HTTP_ACCEPT_LANGUAGE="en")
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        # Raw technical tokens should be cleaned out.
        self.assertNotIn("theta_score", body)
        self.assertNotIn("weakness_detected", body)
        # The humanized phrasing should appear.
        self.assertIn("learning ability score", body)
