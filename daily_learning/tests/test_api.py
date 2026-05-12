"""API tests — only-own-data, completion, history."""
from __future__ import annotations

from django.test import TestCase
from rest_framework.test import APIClient

from daily_learning.models import DailyLearningPlan
from daily_learning.services.daily_plan_generator import generate_for_user

from .factories import make_student


class DailyLearningAPITests(TestCase):
    def setUp(self):
        self.user = make_student(username="apiu", cefr_level="A1")
        self.other = make_student(username="otheru", cefr_level="A1")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_today_endpoint_creates_and_returns_plan(self):
        resp = self.client.get("/api/v1/daily-learning/today/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertGreaterEqual(len(data["items"]), 5)
        self.assertTrue(data["motivation_message"])

    def test_complete_item_endpoint(self):
        plan = generate_for_user(self.user)
        item = plan.items.exclude(item_type="motivation").first()
        resp = self.client.post(
            f"/api/v1/daily-learning/items/{item.id}/complete/",
            {"answer": "x"}, format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["is_completed"])

    def test_history_returns_only_my_plans(self):
        # Create plans for both users
        my_plan = generate_for_user(self.user)
        their_plan = generate_for_user(self.other)
        resp = self.client.get("/api/v1/daily-learning/history/")
        self.assertEqual(resp.status_code, 200)
        ids = {p["id"] for p in resp.json().get("results", resp.json())}
        self.assertIn(my_plan.id, ids)
        self.assertNotIn(their_plan.id, ids)

    def test_cannot_complete_another_users_item(self):
        their_plan = generate_for_user(self.other)
        item = their_plan.items.first()
        resp = self.client.post(
            f"/api/v1/daily-learning/items/{item.id}/complete/",
        )
        self.assertEqual(resp.status_code, 404)

    def test_unauthenticated_blocked(self):
        anon = APIClient()
        resp = anon.get("/api/v1/daily-learning/today/")
        self.assertIn(resp.status_code, (401, 403))
