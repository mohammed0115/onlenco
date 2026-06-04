"""Prompt 5 — digital certificates: eligibility, issuance, public verify."""
import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from courses.models import (
    Course, CourseEnrollment, CourseLessonProgress, CourseLevel,
    DigitalCertificate, Lesson,
)

User = get_user_model()


class _Fixture(TestCase):
    def setUp(self):
        self.level = CourseLevel.objects.create(code="A2", name="A2", order=3)
        self.course = Course.objects.create(
            title="Cert Course", title_en="Cert Course", slug="cert-course",
            level=self.level, status="published", language="bilingual",
        )
        self.l1 = Lesson.objects.create(course=self.course, title="L1", order=1, lesson_type="reading", status="published", is_active=True)
        self.l2 = Lesson.objects.create(course=self.course, title="L2", order=2, lesson_type="reading", status="published", is_active=True)
        self.student = User.objects.create_user("cs", "cs@x.com", "pw12345!")
        p = self.student.profile
        p.full_name = "Test Student"
        p.save(update_fields=["full_name"])
        CourseEnrollment.objects.create(user=self.student, course=self.course)

    def _complete(self, lesson, score=80):
        CourseLessonProgress.objects.create(
            user=self.student, lesson=lesson, video_completed=True,
            quiz_score=score, completed_at=timezone.now(),
        )


class EligibilityTests(_Fixture):
    def test_not_eligible_until_all_lessons_done(self):
        self._complete(self.l1)
        self.assertFalse(DigitalCertificate.is_eligible(self.student, self.course))

    def test_eligible_when_all_lessons_done(self):
        self._complete(self.l1)
        self._complete(self.l2)
        self.assertTrue(DigitalCertificate.is_eligible(self.student, self.course))

    def test_no_lessons_not_eligible(self):
        empty = Course.objects.create(title="Empty", slug="empty", level=self.level, status="published")
        self.assertFalse(DigitalCertificate.is_eligible(self.student, empty))

    def test_average_score(self):
        self._complete(self.l1, 70)
        self._complete(self.l2, 90)
        self.assertEqual(DigitalCertificate.average_score_for(self.student, self.course), 80.0)


class IssueTests(_Fixture):
    def test_issue_snapshots_level_and_score(self):
        self._complete(self.l1, 60)
        self._complete(self.l2, 100)
        cert, created = DigitalCertificate.issue_for(self.student, self.course)
        self.assertTrue(created)
        self.assertEqual(cert.level, "A2")
        self.assertEqual(cert.average_score, 80.0)
        self.assertIsInstance(cert.certificate_uuid, uuid.UUID)

    def test_issue_is_idempotent(self):
        self._complete(self.l1)
        self._complete(self.l2)
        DigitalCertificate.issue_for(self.student, self.course)
        cert2, created2 = DigitalCertificate.issue_for(self.student, self.course)
        self.assertFalse(created2)
        self.assertEqual(DigitalCertificate.objects.filter(student=self.student, course=self.course).count(), 1)


class PublicViewTests(_Fixture):
    def _cert(self):
        self._complete(self.l1)
        self._complete(self.l2)
        return DigitalCertificate.issue_for(self.student, self.course)[0]

    def test_verify_valid_uuid(self):
        cert = self._cert()
        r = self.client.get(f"/courses/verify/{cert.certificate_uuid}/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Test Student")  # profile name shown

    def test_public_pages_never_leak_email(self):
        # P0 guard: the public certificate + verify pages must NOT expose the
        # student's email / username.
        cert = self._cert()
        for path in (f"/courses/certificate/{cert.certificate_uuid}/",
                     f"/courses/verify/{cert.certificate_uuid}/"):
            html = self.client.get(path).content.decode()
            self.assertNotIn("cs@x.com", html)
            self.assertIn("Test Student", html)

    def test_verify_unknown_uuid_shows_not_found(self):
        unknown = uuid.uuid4()
        r = self.client.get(f"/courses/verify/{unknown}/")
        self.assertEqual(r.status_code, 200)
        # Not-found state: no verified badge (either language), and the
        # queried id is echoed back.
        self.assertNotContains(r, "Verified certificate")
        self.assertNotContains(r, "موثّقة")
        self.assertContains(r, str(unknown))

    def test_certificate_detail_renders(self):
        cert = self._cert()
        r = self.client.get(f"/courses/certificate/{cert.certificate_uuid}/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Cert Course")

    def test_certificates_list_requires_login(self):
        r = self.client.get("/courses/certificates/")
        self.assertEqual(r.status_code, 302)
