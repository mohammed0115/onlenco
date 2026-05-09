from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from tutor.models import TutorConversation, TutorMessage

User = get_user_model()


@override_settings(AXES_ENABLED=False)
class ConversationListTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="tu@x.com", email="tu@x.com", password="pw"
        )
        # Subscribe so the gate doesn't redirect to /payments/
        prof = self.user.profile
        prof.subscription_status = "active"
        prof.subscription_expires_at = timezone.now() + timezone.timedelta(days=30)
        prof.save()

        self.client.login(username="tu@x.com", password="pw")

    def test_empty_drafts_are_hidden(self):
        with_msgs = TutorConversation.objects.create(user=self.user, title="real")
        TutorMessage.objects.create(conversation=with_msgs, role="user", content="hi")
        TutorConversation.objects.create(user=self.user)  # draft

        resp = self.client.get(reverse("tutor"))
        self.assertEqual(resp.status_code, 200)
        listed = list(resp.context["conversations"])
        self.assertEqual([c.pk for c in listed], [with_msgs.pk])

    def test_new_button_reuses_empty_draft(self):
        draft = TutorConversation.objects.create(user=self.user)
        resp = self.client.post(reverse("tutor_new"))
        self.assertRedirects(resp, reverse("tutor_detail", args=[draft.pk]))
        self.assertEqual(TutorConversation.objects.filter(user=self.user).count(), 1)

    def test_new_button_creates_when_no_draft(self):
        existing = TutorConversation.objects.create(user=self.user, title="t")
        TutorMessage.objects.create(conversation=existing, role="user", content="hi")

        resp = self.client.post(reverse("tutor_new"))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(TutorConversation.objects.filter(user=self.user).count(), 2)

    def test_new_button_updates_topic_on_reused_draft(self):
        draft = TutorConversation.objects.create(user=self.user)
        resp = self.client.post(reverse("tutor_new"), {"topic": "grammar"})
        self.assertRedirects(resp, reverse("tutor_detail", args=[draft.pk]))
        draft.refresh_from_db()
        self.assertEqual(draft.topic, "grammar")
