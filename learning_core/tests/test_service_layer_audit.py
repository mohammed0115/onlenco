"""Audit: confirm each major app exposes a callable service layer.

This guards against future drift where business logic creeps back into views.
"""
from importlib import import_module

from django.test import TestCase


class ServiceLayerAuditTests(TestCase):
    def test_required_service_modules_importable(self):
        modules = [
            "accounts.services",
            "lessons.services.adaptive_quiz_adapter",
            "learning_core.services.error_analyzer",
            "learning_core.services.weakness_engine",
            "learning_core.services.adaptive_difficulty",
            "learning_core.services.exercise_generator",
            "learning_core.services.recommendation_engine",
            "placement.services.diagnostic_engine",
            "tutor.services.context_builder",
            "payments.services",
            "analytics.services_learning",
        ]
        for path in modules:
            with self.subTest(module=path):
                import_module(path)

    def test_payments_services_expose_orchestrators(self):
        from payments import services as payment_services
        self.assertTrue(callable(getattr(payment_services, "approve_submission")))
        self.assertTrue(callable(getattr(payment_services, "reject_submission")))

    def test_accounts_register_callable(self):
        from accounts.services import register_user
        u = register_user(username="svc_test", email="svc@test", password="pw", full_name="S T")
        self.assertEqual(u.username, "svc_test")
        self.assertEqual(u.profile.full_name, "S T")
