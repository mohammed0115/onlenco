from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.models import Profile
from accounts.services import register_user

User = get_user_model()


class AccountsTests(TestCase):
    def test_register_user_creates_profile(self):
        u = register_user(username="kaz", email="k@z", password="pw", full_name="Ka Zoo")
        self.assertEqual(u.profile.full_name, "Ka Zoo")
        self.assertEqual(u.profile.preferred_language, "en")
        self.assertEqual(u.profile.role, "student")

    def test_profile_auto_created_on_user_create(self):
        u = User.objects.create_user(username="auto", password="pw")
        self.assertTrue(Profile.objects.filter(user=u).exists())

    def test_login_works(self):
        u = User.objects.create_user(username="login", password="pw123456")
        ok = self.client.login(username="login", password="pw123456")
        self.assertTrue(ok)
