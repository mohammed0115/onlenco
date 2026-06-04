"""Prompt 1 — Teacher Marketplace: teacher selection + revenue split.

Additive, backward-compatible: no test here gates lesson access, and the
existing approval flow keeps working (the split defaults the whole amount to
the platform when no teacher is chosen).
"""
from io import BytesIO

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from payments.models import PaymentSubmission
from teacher_portal.models import StudentTeacherRelation, TeacherProfile

User = get_user_model()


def _png():
    from django.core.files.uploadedfile import SimpleUploadedFile
    from PIL import Image
    buf = BytesIO()
    Image.new("RGBA", (1, 1), (255, 255, 255, 0)).save(buf, format="PNG")
    return SimpleUploadedFile("x.png", buf.getvalue(), content_type="image/png")


class _Base(TestCase):
    def setUp(self):
        self.student = User.objects.create_user("stud", "s@x.com", "pw12345!")
        self.student.profile.cefr_level = "A2"
        self.student.profile.save(update_fields=["cefr_level"])
        self.admin = User.objects.create_user("adm", "a@x.com", "pw12345!", is_staff=True, is_superuser=True)

    def _teacher(self, username, *, approved=True, active=True, featured=False, rating="4.5", commission=30, focus="", rate=0):
        u = User.objects.create_user(username, f"{username}@x.com", "pw12345!")
        TeacherProfile.objects.create(
            user=u, is_active=active,
            approved_at=timezone.now() if approved else None,
            is_featured=featured, rating=rating, commission_rate=commission,
            cefr_focus=focus, hourly_rate_sdg=rate, bio_en=f"{username} bio",
        )
        return u

    def _submission(self, amount=30000, status="pending"):
        return PaymentSubmission.objects.create(
            user=self.student, plan="monthly", method="bankak",
            transaction_reference="ref", amount_sdg=amount,
            screenshot=_png(), status=status,
        )


class RevenueSplitTests(_Base):
    def test_split_70_30_with_selected_teacher(self):
        teacher = self._teacher("teach1", commission=30)
        StudentTeacherRelation.set_active(self.student, teacher, cefr_level="A2")
        sub = self._submission(amount=30000)
        sub.approve(self.admin)
        self.assertEqual(sub.teacher_earnings, 21000)   # 70%
        self.assertEqual(sub.platform_earnings, 9000)   # 30%
        self.assertEqual(sub.teacher_earnings + sub.platform_earnings, 30000)

    def test_custom_commission_rate(self):
        teacher = self._teacher("teach2", commission=20)
        StudentTeacherRelation.set_active(self.student, teacher)
        sub = self._submission(amount=50000)
        sub.approve(self.admin)
        self.assertEqual(sub.teacher_earnings, 40000)   # 80%
        self.assertEqual(sub.platform_earnings, 10000)  # 20%

    def test_no_teacher_all_to_platform(self):
        sub = self._submission(amount=30000)
        sub.approve(self.admin)
        self.assertEqual(sub.teacher_earnings, 0)
        self.assertEqual(sub.platform_earnings, 30000)

    def test_rounding_remainder_goes_to_platform(self):
        teacher = self._teacher("teach3", commission=33)
        StudentTeacherRelation.set_active(self.student, teacher)
        sub = self._submission(amount=10001)
        sub.approve(self.admin)
        # teacher = 10001*67//100 = 6700 ; platform gets the rest
        self.assertEqual(sub.teacher_earnings, 6700)
        self.assertEqual(sub.platform_earnings, 3301)
        self.assertEqual(sub.teacher_earnings + sub.platform_earnings, 10001)

    def test_approval_still_activates_subscription(self):
        # Regression: marketplace layer must not break the legacy approve.
        sub = self._submission()
        sub.approve(self.admin)
        self.assertEqual(sub.status, "approved")
        self.student.profile.refresh_from_db()
        self.assertEqual(self.student.profile.subscription_status, "active")


class RefundAndIntegrityTests(_Base):
    def test_refund_zeroes_recorded_earnings(self):
        teacher = self._teacher("rt", commission=30)
        StudentTeacherRelation.set_active(self.student, teacher)
        sub = self._submission(amount=30000)
        sub.approve(self.admin)
        self.assertEqual(sub.teacher_earnings, 21000)
        sub.refund(self.admin, reason="duplicate")
        sub.refresh_from_db()
        self.assertEqual(sub.status, "refunded")
        self.assertEqual(sub.teacher_earnings, 0)
        self.assertEqual(sub.platform_earnings, 0)

    def test_unique_constraint_blocks_duplicate_relation(self):
        from django.db import IntegrityError, transaction
        teacher = self._teacher("uq")
        StudentTeacherRelation.objects.create(student=self.student, teacher=teacher)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                StudentTeacherRelation.objects.create(student=self.student, teacher=teacher)

    def test_set_active_is_idempotent_no_duplicate_rows(self):
        teacher = self._teacher("idem")
        StudentTeacherRelation.set_active(self.student, teacher)
        StudentTeacherRelation.set_active(self.student, teacher)
        self.assertEqual(
            StudentTeacherRelation.objects.filter(student=self.student, teacher=teacher).count(), 1,
        )

    def test_single_active_relation_after_switch(self):
        t1, t2 = self._teacher("s1"), self._teacher("s2")
        StudentTeacherRelation.set_active(self.student, t1)
        StudentTeacherRelation.set_active(self.student, t2)
        self.assertEqual(StudentTeacherRelation.objects.filter(student=self.student, is_active=True).count(), 1)
        self.assertEqual(StudentTeacherRelation.active_for(self.student).teacher_id, t2.pk)


class TeacherShareHelperTests(_Base):
    def test_teacher_and_platform_share_sum_to_amount(self):
        tp = self._teacher("h", commission=25).teacher_profile
        self.assertEqual(tp.teacher_share(40000), 30000)
        self.assertEqual(tp.platform_share(40000), 10000)

    def test_teaches_level_blank_focus_matches_all(self):
        tp = self._teacher("h2", focus="").teacher_profile
        self.assertTrue(tp.teaches_level("A2"))
        self.assertTrue(tp.teaches_level("C1"))

    def test_teaches_level_respects_focus(self):
        tp = self._teacher("h3", focus="A0,A1,A2").teacher_profile
        self.assertTrue(tp.teaches_level("A2"))
        self.assertFalse(tp.teaches_level("B2"))


class ChooseTeacherViewTests(_Base):
    def test_page_lists_matching_candidates(self):
        self._teacher("beg1", focus="A0,A1,A2", featured=True)
        self._teacher("beg2", focus="A2,B1")
        self._teacher("adv", focus="C1,C2")  # should not match A2
        self.client.force_login(self.student)
        html = self.client.get("/payments/choose-teacher/").content.decode()
        self.assertIn("beg1", html)
        self.assertIn("beg2", html)
        self.assertNotIn(">adv<", html)

    def test_unapproved_or_inactive_teacher_hidden(self):
        self._teacher("pending", approved=False)
        self._teacher("disabled", active=False)
        self.client.force_login(self.student)
        html = self.client.get("/payments/choose-teacher/").content.decode()
        self.assertNotIn("pending bio", html)
        self.assertNotIn("disabled bio", html)

    def test_select_teacher_creates_active_relation(self):
        teacher = self._teacher("pick")
        self.client.force_login(self.student)
        r = self.client.post("/payments/choose-teacher/", {"teacher_id": teacher.pk})
        self.assertEqual(r.status_code, 302)
        rel = StudentTeacherRelation.active_for(self.student)
        self.assertIsNotNone(rel)
        self.assertEqual(rel.teacher_id, teacher.pk)
        self.assertEqual(rel.cefr_level_at_selection, "A2")

    def test_selecting_new_teacher_deactivates_previous(self):
        t1 = self._teacher("t1")
        t2 = self._teacher("t2")
        StudentTeacherRelation.set_active(self.student, t1)
        self.client.force_login(self.student)
        self.client.post("/payments/choose-teacher/", {"teacher_id": t2.pk})
        active = StudentTeacherRelation.objects.filter(student=self.student, is_active=True)
        self.assertEqual(active.count(), 1)
        self.assertEqual(active.first().teacher_id, t2.pk)

    def test_requires_login(self):
        r = self.client.get("/payments/choose-teacher/")
        self.assertEqual(r.status_code, 302)  # anonymous → redirected to login
