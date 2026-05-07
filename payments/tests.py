from django.test import TestCase

from payments.models import PaymentMethodAccount


class PaymentMethodAccountSeedTest(TestCase):
    def test_three_methods_seeded(self):
        codes = set(PaymentMethodAccount.objects.values_list("method", flat=True))
        self.assertEqual(codes, {"bankak", "fawry", "ocash"})
