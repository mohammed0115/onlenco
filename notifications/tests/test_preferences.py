from django.contrib.auth import get_user_model
from django.test import TestCase

from notifications import constants as C
from notifications.services.preference_service import PreferenceService

User = get_user_model()


class PreferenceServiceTests(TestCase):
    def setUp(self):
        self.svc = PreferenceService()
        self.user = User.objects.create_user(username="p1", email="p1@x", password="pw")

    def test_no_email_blocks_all(self):
        u = User.objects.create_user(username="noemail", password="pw")
        self.assertFalse(self.svc.can_send(u, C.WELCOME if hasattr(C, "WELCOME") else C.LESSON_COMPLETED))

    def test_transactional_bypasses_preferences(self):
        pref = self.svc.get_or_create_for(self.user)
        pref.payment_updates = False
        pref.save()
        # PAYMENT_APPROVED is transactional → must still be allowed
        self.assertTrue(self.svc.can_send(self.user, C.PAYMENT_APPROVED))
        self.assertTrue(self.svc.can_send(self.user, C.PASSWORD_RESET))

    def test_learning_event_respects_toggle(self):
        pref = self.svc.get_or_create_for(self.user)
        pref.learning_updates = False
        pref.save()
        self.assertFalse(self.svc.can_send(self.user, C.LESSON_COMPLETED))
        pref.learning_updates = True
        pref.save()
        self.assertTrue(self.svc.can_send(self.user, C.LESSON_COMPLETED))

    def test_admin_event_requires_admin_recipient(self):
        # Plain student
        self.assertFalse(self.svc.can_send(self.user, C.NEW_PAYMENT_PENDING))
        # Promote
        self.user.is_staff = True
        self.user.save()
        self.assertTrue(self.svc.can_send(self.user, C.NEW_PAYMENT_PENDING))
        # Disable admin alerts
        pref = self.svc.get_or_create_for(self.user)
        pref.admin_alerts = False
        pref.save()
        self.assertFalse(self.svc.can_send(self.user, C.NEW_PAYMENT_PENDING))

    def test_get_language_defaults_to_profile_lang(self):
        self.user.profile.preferred_language = "ar"
        self.user.profile.save()
        # Force fresh preference creation
        from notifications.models import NotificationPreference
        NotificationPreference.objects.filter(user=self.user).delete()
        self.assertEqual(self.svc.get_language(self.user), "ar")
