"""Prompt 2 — live sessions: scheduling cap, Meet link, notifications, reminders."""
from datetime import timedelta

from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone

from notifications import constants as C
from notifications.models import NotificationEvent
from teacher_portal.forms import LiveSessionForm
from teacher_portal.models import LiveSession
from teacher_portal.services import live_session_service, meet_service
from teacher_portal.tests.utils import TeacherPortalTestMixin


def _future(minutes=24 * 60):
    return timezone.now() + timedelta(minutes=minutes)


class MeetServiceTests(TeacherPortalTestMixin):
    def test_mock_link_shape(self):
        link = meet_service.generate_meet_link(title="X", start=_future(), duration_minutes=60)
        self.assertTrue(link.startswith("https://meet.google.com/"))
        self.assertRegex(link, r"^https://meet\.google\.com/[a-f0-9]{3}-[a-f0-9]{4}-[a-f0-9]{3}$")

    def test_links_are_unique(self):
        a = meet_service.generate_meet_link(title="A", start=_future())
        b = meet_service.generate_meet_link(title="B", start=_future())
        self.assertNotEqual(a, b)


class WeeklyLimitTests(TeacherPortalTestMixin):
    def _make(self, when):
        return LiveSession.objects.create(
            teacher=self.teacher, course=self.course, title="S",
            scheduled_at=when, meet_link="https://meet.google.com/aaa-bbbb-ccc",
        )

    def test_third_session_same_week_is_rejected(self):
        base = _future(60)
        self._make(base)
        self._make(base + timedelta(hours=2))
        form = LiveSessionForm(
            data={"course": self.course.pk, "title": "Third", "description": "",
                  "scheduled_at": (base + timedelta(hours=4)).strftime("%Y-%m-%dT%H:%M"),
                  "duration_minutes": 60},
            teacher=self.teacher,
        )
        self.assertFalse(form.is_valid())

    def test_cancelled_sessions_do_not_count(self):
        base = _future(60)
        self._make(base)
        s2 = self._make(base + timedelta(hours=2))
        s2.status = "cancelled"
        s2.save(update_fields=["status"])
        form = LiveSessionForm(
            data={"course": self.course.pk, "title": "OK", "description": "",
                  "scheduled_at": (base + timedelta(hours=4)).strftime("%Y-%m-%dT%H:%M"),
                  "duration_minutes": 60},
            teacher=self.teacher,
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_past_datetime_rejected(self):
        form = LiveSessionForm(
            data={"course": self.course.pk, "title": "Past", "description": "",
                  "scheduled_at": (timezone.now() - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M"),
                  "duration_minutes": 60},
            teacher=self.teacher,
        )
        self.assertFalse(form.is_valid())

    def test_form_scopes_courses_to_teacher(self):
        form = LiveSessionForm(teacher=self.teacher)
        course_ids = set(form.fields["course"].queryset.values_list("pk", flat=True))
        self.assertIn(self.course.pk, course_ids)
        self.assertNotIn(self.other_course.pk, course_ids)


class ScheduleViewTests(TeacherPortalTestMixin):
    def test_create_generates_meet_link_and_notifies_students(self):
        self.client.force_login(self.teacher)
        before = NotificationEvent.objects.filter(event_type=C.LIVE_SESSION_SCHEDULED).count()
        r = self.client.post("/teacher/live-sessions/create/", {
            "course": self.course.pk, "title": "Intro call", "description": "Welcome",
            "scheduled_at": _future().strftime("%Y-%m-%dT%H:%M"), "duration_minutes": 45,
        })
        self.assertEqual(r.status_code, 302)
        session = LiveSession.objects.get(course=self.course, title="Intro call")
        self.assertEqual(session.teacher, self.teacher)
        self.assertTrue(session.meet_link.startswith("https://meet.google.com/"))
        after = NotificationEvent.objects.filter(event_type=C.LIVE_SESSION_SCHEDULED).count()
        self.assertEqual(after - before, 1)  # one active student enrolled in self.course

    def test_list_page_renders(self):
        self.client.force_login(self.teacher)
        LiveSession.objects.create(teacher=self.teacher, course=self.course, title="MySession", scheduled_at=_future())
        r = self.client.get("/teacher/live-sessions/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "MySession")
        self.assertContains(r, "live-sessions/create")

    def test_cancel_session(self):
        self.client.force_login(self.teacher)
        s = LiveSession.objects.create(teacher=self.teacher, course=self.course, title="X", scheduled_at=_future())
        r = self.client.post(f"/teacher/live-sessions/{s.pk}/cancel/")
        self.assertEqual(r.status_code, 302)
        s.refresh_from_db()
        self.assertEqual(s.status, "cancelled")


class ReminderTests(TeacherPortalTestMixin):
    def test_due_reminder_sent_once(self):
        s = LiveSession.objects.create(
            teacher=self.teacher, course=self.course, title="Soon",
            scheduled_at=timezone.now() + timedelta(minutes=20),
        )
        result = live_session_service.send_reminders()
        self.assertEqual(result["sessions"], 1)
        self.assertEqual(result["students"], 1)  # self.student enrolled active
        s.refresh_from_db()
        self.assertIsNotNone(s.reminder_sent_at)
        self.assertTrue(NotificationEvent.objects.filter(event_type=C.LIVE_SESSION_REMINDER).exists())
        # Idempotent: a second run sends nothing.
        again = live_session_service.send_reminders()
        self.assertEqual(again["sessions"], 0)

    def test_just_past_session_still_reminded_within_grace(self):
        # A late cron tick: the session just crossed "now" but is within the
        # grace floor → it must still be reminded, not lost forever.
        LiveSession.objects.create(
            teacher=self.teacher, course=self.course, title="JustStarted",
            scheduled_at=timezone.now() - timedelta(minutes=5),
        )
        result = live_session_service.send_reminders()
        self.assertEqual(result["sessions"], 1)

    def test_long_past_session_not_reminded(self):
        LiveSession.objects.create(
            teacher=self.teacher, course=self.course, title="Old",
            scheduled_at=timezone.now() - timedelta(minutes=40),
        )
        result = live_session_service.send_reminders()
        self.assertEqual(result["sessions"], 0)

    def test_far_future_session_not_reminded(self):
        LiveSession.objects.create(
            teacher=self.teacher, course=self.course, title="Later",
            scheduled_at=timezone.now() + timedelta(hours=5),
        )
        result = live_session_service.send_reminders()
        self.assertEqual(result["sessions"], 0)

    def test_management_command_runs(self):
        LiveSession.objects.create(
            teacher=self.teacher, course=self.course, title="Soon",
            scheduled_at=timezone.now() + timedelta(minutes=10),
        )
        call_command("send_live_session_reminders")
        self.assertTrue(NotificationEvent.objects.filter(event_type=C.LIVE_SESSION_REMINDER).exists())
