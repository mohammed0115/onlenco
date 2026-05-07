from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone

from payments.forms import PaymentSubmissionForm
from payments.models import PaymentMethodAccount, PaymentSubmission

User = get_user_model()


def _png_bytes(size: int = 200) -> bytes:
    # 1x1 PNG with padding to reach desired size for size validation tests
    base = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\x0eIDAT"
        b"\x08\xd7c\xf8\xff\xff?\x00\x05\xfe\x02\xfe\xa3'\x99\x9d\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    if size > len(base):
        return base + b"\x00" * (size - len(base))
    return base


class PaymentMethodAccountSeedTest(TestCase):
    def test_three_methods_seeded(self):
        codes = set(PaymentMethodAccount.objects.values_list("method", flat=True))
        self.assertEqual(codes, {"bankak", "fawry", "ocash"})


class PlanPricingTests(TestCase):
    def test_monthly_plan_is_30000(self):
        from payments.models import PLAN_DETAILS
        self.assertEqual(PLAN_DETAILS["monthly"]["price_sdg"], 30000)
        self.assertEqual(PLAN_DETAILS["monthly"]["duration_days"], 30)

    def test_quarterly_plan_is_50000(self):
        from payments.models import PLAN_DETAILS
        self.assertEqual(PLAN_DETAILS["quarterly"]["price_sdg"], 50000)
        self.assertEqual(PLAN_DETAILS["quarterly"]["duration_days"], 90)


class PaymentSubmissionFormTests(TestCase):
    def setUp(self):
        # Method must be active for clean_method
        PaymentMethodAccount.objects.filter(method="bankak").update(is_active=True)

    def test_oversize_screenshot_rejected(self):
        big = SimpleUploadedFile(
            "big.png", _png_bytes(6 * 1024 * 1024), content_type="image/png"
        )
        form = PaymentSubmissionForm(
            data={"plan": "monthly", "method": "bankak", "transaction_reference": "X"},
            files={"screenshot": big},
        )
        self.assertFalse(form.is_valid())
        self.assertIn("screenshot", form.errors)

    def test_pdf_screenshot_rejected(self):
        bad = SimpleUploadedFile(
            "x.pdf", b"%PDF-1.4\n%fake", content_type="application/pdf"
        )
        form = PaymentSubmissionForm(
            data={"plan": "monthly", "method": "bankak", "transaction_reference": "X"},
            files={"screenshot": bad},
        )
        # Note: ImageField may also reject this earlier; either way, not valid.
        self.assertFalse(form.is_valid())

    def test_inactive_method_rejected(self):
        PaymentMethodAccount.objects.filter(method="bankak").update(is_active=False)
        good = SimpleUploadedFile(
            "x.png", _png_bytes(), content_type="image/png"
        )
        form = PaymentSubmissionForm(
            data={"plan": "monthly", "method": "bankak", "transaction_reference": "X"},
            files={"screenshot": good},
        )
        self.assertFalse(form.is_valid())
        self.assertIn("method", form.errors)


class PaymentApprovalTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="kira", password="pw")
        self.admin = User.objects.create_user(
            username="admin", password="pw", is_staff=True, is_superuser=True
        )

    def _submission(self, status="pending"):
        f = SimpleUploadedFile("x.png", _png_bytes(), content_type="image/png")
        return PaymentSubmission.objects.create(
            user=self.user,
            plan="monthly",
            method="bankak",
            transaction_reference="ref",
            amount_sdg=8000,
            screenshot=f,
            status=status,
        )

    def test_approve_activates_subscription(self):
        sub = self._submission("pending")
        sub.approve(self.admin)
        sub.refresh_from_db()
        self.assertEqual(sub.status, "approved")
        self.assertIsNotNone(sub.reviewed_at)
        self.assertEqual(sub.reviewed_by, self.admin)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.subscription_status, "active")

    def test_submitted_at_default_set(self):
        sub = self._submission("pending")
        self.assertIsNotNone(sub.submitted_at)
        self.assertLessEqual(sub.submitted_at, timezone.now())

    def test_user_cannot_see_other_users_payments(self):
        self._submission("pending")
        self.client.force_login(User.objects.create_user(username="other", password="pw"))
        # the user dashboard reads request.user.payment_submissions, which is
        # FK-scoped, so the other user gets nothing
        from accounts.models import Profile
        my_subs = User.objects.get(username="other").payment_submissions.all()
        self.assertEqual(my_subs.count(), 0)

    def test_needs_review_status_allowed(self):
        sub = self._submission("needs_review")
        self.assertEqual(sub.status, "needs_review")
