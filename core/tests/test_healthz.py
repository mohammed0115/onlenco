from django.test import TestCase
from django.urls import reverse


class HealthzTests(TestCase):
    def test_healthz_returns_ok(self):
        r = self.client.get(reverse("healthz"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"status": "ok"})
