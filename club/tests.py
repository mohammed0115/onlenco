"""Club attendance + feedback tests."""
from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from club.models import ClubEvent, ClubFeedback, ClubRSVP
from club.services import (
    event_attendance_summary,
    mark_attendance,
    submit_feedback,
)


User = get_user_model()


class ClubAttendanceTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(username="t@x.com", email="t@x.com", password="pw", is_staff=True)
        self.student = User.objects.create_user(username="s@x.com", email="s@x.com", password="pw")
        self.event = ClubEvent.objects.create(
            title="Speaking Club", topic="Daily routine",
            starts_at=timezone.now() + timedelta(days=1),
            capacity=10,
        )
        self.rsvp = ClubRSVP.objects.create(event=self.event, user=self.student, status="going")

    def test_mark_attendance_sets_audit_fields(self):
        mark_attendance(rsvp=self.rsvp, marked_by=self.teacher, attended=True)
        self.rsvp.refresh_from_db()
        self.assertTrue(self.rsvp.attended)
        self.assertIsNotNone(self.rsvp.attendance_marked_at)
        self.assertEqual(self.rsvp.attendance_marked_by_id, self.teacher.pk)

    def test_unmark_attendance_clears_audit_fields(self):
        mark_attendance(rsvp=self.rsvp, marked_by=self.teacher, attended=True)
        mark_attendance(rsvp=self.rsvp, marked_by=self.teacher, attended=False)
        self.rsvp.refresh_from_db()
        self.assertFalse(self.rsvp.attended)
        self.assertIsNone(self.rsvp.attendance_marked_at)
        self.assertIsNone(self.rsvp.attendance_marked_by_id)

    def test_attendance_summary_counts(self):
        # 3 students, 2 going + 1 maybe; 1 attended.
        u2 = User.objects.create_user(username="s2@x.com", email="s2@x.com", password="pw")
        u3 = User.objects.create_user(username="s3@x.com", email="s3@x.com", password="pw")
        ClubRSVP.objects.create(event=self.event, user=u2, status="going")
        ClubRSVP.objects.create(event=self.event, user=u3, status="maybe")
        mark_attendance(rsvp=self.rsvp, marked_by=self.teacher, attended=True)
        summary = event_attendance_summary(self.event)
        self.assertEqual(summary["registered"], 3)
        self.assertEqual(summary["going"], 2)
        self.assertEqual(summary["attended"], 1)
        self.assertEqual(summary["no_show"], 1)


class ClubFeedbackTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(username="ft@x.com", email="ft@x.com", password="pw", is_staff=True)
        self.student = User.objects.create_user(username="fs@x.com", email="fs@x.com", password="pw")
        self.event = ClubEvent.objects.create(
            title="Club", topic="Travel",
            starts_at=timezone.now() - timedelta(hours=1),
        )

    def test_submit_feedback_creates_row(self):
        fb = submit_feedback(
            event=self.event, student=self.student, author=self.teacher,
            rating=4, feedback_en="Great participation.",
        )
        self.assertEqual(fb.rating, 4)
        self.assertEqual(fb.feedback_en, "Great participation.")
        self.assertEqual(ClubFeedback.objects.count(), 1)

    def test_resubmit_feedback_updates_existing_row(self):
        submit_feedback(event=self.event, student=self.student, author=self.teacher, rating=3)
        submit_feedback(event=self.event, student=self.student, author=self.teacher, rating=5, feedback_en="Improved.")
        self.assertEqual(ClubFeedback.objects.count(), 1)
        fb = ClubFeedback.objects.get()
        self.assertEqual(fb.rating, 5)
        self.assertEqual(fb.feedback_en, "Improved.")

    def test_rating_clamped_to_1_5(self):
        fb = submit_feedback(event=self.event, student=self.student, author=self.teacher, rating=99)
        self.assertEqual(fb.rating, 5)
        fb2 = submit_feedback(event=self.event, student=self.student, author=self.teacher, rating=-3)
        self.assertEqual(fb2.rating, 1)

    def test_one_feedback_per_student_per_event(self):
        u2 = User.objects.create_user(username="fb2@x.com", email="fb2@x.com", password="pw")
        submit_feedback(event=self.event, student=self.student, author=self.teacher, rating=3)
        submit_feedback(event=self.event, student=u2, author=self.teacher, rating=3)
        # Different students → 2 rows; same student again would update, not add.
        self.assertEqual(ClubFeedback.objects.count(), 2)
