from dataclasses import replace
from decimal import Decimal
import unittest

from pretix_checkout_assistant.invoice_policy import InvoiceFacts, InvoiceMode, invoice_mode


class SmallInvoicePolicyTests(unittest.TestCase):
    def setUp(self):
        self.facts = InvoiceFacts(
            gross_total=Decimal("250.00"), currency="EUR", price_final=True,
            german_rule_approved=True, exception_3c=False, exception_6a=False,
            exception_13b=False, customer_requests_full=False,
        )

    def test_boundary(self):
        for amount, expected in (("249.99", InvoiceMode.SMALL_AMOUNT_CANDIDATE),
                                 ("250.00", InvoiceMode.SMALL_AMOUNT_CANDIDATE),
                                 ("250.01", InvoiceMode.FULL)):
            with self.subTest(amount=amount):
                self.assertIs(invoice_mode(replace(self.facts, gross_total=amount)), expected)

    def test_unknown_and_exception_fall_back(self):
        for field in ("exception_3c", "exception_6a", "exception_13b"):
            for value in (True, None):
                with self.subTest(field=field, value=value):
                    self.assertIs(invoice_mode(replace(self.facts, **{field: value})), InvoiceMode.FULL)

    def test_other_prerequisites(self):
        for changes in ({"currency": "USD"}, {"price_final": False},
                        {"german_rule_approved": False}, {"customer_requests_full": True},
                        {"customer_requests_full": None}):
            with self.subTest(changes=changes):
                self.assertIs(invoice_mode(replace(self.facts, **changes)), InvoiceMode.FULL)

    def test_invalid_and_free_totals_fail_closed(self):
        for amount in (None, "NaN", "Infinity", "-1", "0", "250.001", 250.0, True):
            with self.subTest(amount=amount):
                self.assertIs(invoice_mode(replace(self.facts, gross_total=amount)), InvoiceMode.FULL)


if __name__ == "__main__":
    unittest.main()

