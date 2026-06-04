"""Login honours a safe ?next= destination (deep-linking) after onboarding."""
from django.contrib.auth import get_user_model
from django.test import TestCase

User = get_user_model()


class PostLoginNextTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.user = User.objects.create_user("nx", "nx@x.com", "pw12345!")
        # Clear every onboarding gate so next_url_for() returns None and the
        # ?next destination is what's exercised.
        p = self.user.profile
        p.email_verified = True
        p.onboarding_completed = True
        p.placement_completed = True
        p.save()

    def test_authenticated_get_with_next_redirects_there(self):
        self.client.force_login(self.user)
        r = self.client.get("/auth/?next=/courses/certificates/")
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, "/courses/certificates/")

    def test_external_next_is_ignored(self):
        self.client.force_login(self.user)
        r = self.client.get("/auth/?next=https://evil.example.com/x")
        self.assertEqual(r.status_code, 302)
        self.assertNotIn("evil.example.com", r.url)

    def test_no_next_falls_back_to_default(self):
        self.client.force_login(self.user)
        r = self.client.get("/auth/")
        self.assertEqual(r.status_code, 302)
        self.assertNotEqual(r.url, "")
