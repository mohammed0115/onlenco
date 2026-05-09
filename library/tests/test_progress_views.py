from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from library.models import Book, Chapter, ComprehensionQuestion, LibraryProgress

User = get_user_model()


@override_settings(AXES_ENABLED=False)
class LibraryProgressViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="reader@x.com", email="reader@x.com", password="pw"
        )
        prof = self.user.profile
        prof.subscription_status = "active"
        prof.subscription_expires_at = timezone.now() + timezone.timedelta(days=30)
        prof.save()

        self.book = Book.objects.create(
            title="The Test Book", author="Test", category="novel", level="A2",
        )
        self.chapter = Chapter.objects.create(
            book=self.book, title="Chapter 1", body="Some text. " * 50, sort_order=1,
        )
        self.q = ComprehensionQuestion.objects.create(
            chapter=self.chapter, question="What is the body's word?",
            correct_answer="some", explanation="It says 'some'.",
        )
        self.client.login(username="reader@x.com", password="pw")

    def test_update_position_creates_progress(self):
        url = reverse("library_update_position", args=[self.chapter.id])
        resp = self.client.post(url, {"position": "120"})
        self.assertEqual(resp.status_code, 200)
        prog = LibraryProgress.objects.get(user=self.user, chapter=self.chapter)
        self.assertEqual(prog.last_position, 120)

    def test_position_only_advances(self):
        url = reverse("library_update_position", args=[self.chapter.id])
        self.client.post(url, {"position": "200"})
        self.client.post(url, {"position": "50"})
        prog = LibraryProgress.objects.get(user=self.user, chapter=self.chapter)
        self.assertEqual(prog.last_position, 200)

    def test_mark_complete(self):
        url = reverse("library_chapter_complete", args=[self.chapter.id])
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 302)
        prog = LibraryProgress.objects.get(user=self.user, chapter=self.chapter)
        self.assertTrue(prog.completed)

    def test_submit_comprehension_grades_correctly(self):
        url = reverse("library_submit_comprehension", args=[self.chapter.id])
        resp = self.client.post(url, {f"q_{self.q.id}": "some"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["correct"], 1)
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["score"], 100)
        prog = LibraryProgress.objects.get(user=self.user, chapter=self.chapter)
        self.assertEqual(prog.comprehension_score, 100)
        self.assertTrue(prog.completed)

    def test_submit_comprehension_wrong_answer(self):
        url = reverse("library_submit_comprehension", args=[self.chapter.id])
        resp = self.client.post(url, {f"q_{self.q.id}": "wrong"})
        data = resp.json()
        self.assertEqual(data["correct"], 0)
        self.assertEqual(data["score"], 0)

    def test_unsubscribed_blocked_from_progress_endpoints(self):
        prof = self.user.profile
        prof.subscription_status = "inactive"
        prof.save()
        resp = self.client.post(
            reverse("library_update_position", args=[self.chapter.id]),
            {"position": "10"},
        )
        self.assertEqual(resp.status_code, 403)
