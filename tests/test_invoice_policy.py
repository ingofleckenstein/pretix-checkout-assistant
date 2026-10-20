from dataclasses import replace
from decimal import Decimal
import unittest

from pretix_checkout_assistant.invoice_policy import (
    InvoiceFacts, InvoiceMode, early_invoice_mode, guest_invoice_mode, invoice_mode,
)


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

    def test_early_buffer_and_final_recheck_are_distinct(self):
        for amount, expected in (("199.99", InvoiceMode.SMALL_AMOUNT_CANDIDATE),
                                 ("200.00", InvoiceMode.SMALL_AMOUNT_CANDIDATE),
                                 ("200.01", InvoiceMode.FULL)):
            with self.subTest(amount=amount):
                self.assertIs(early_invoice_mode(replace(self.facts, gross_total=amount, price_final=False)), expected)
        early = replace(self.facts, gross_total="200.00", price_final=False)
        self.assertIs(early_invoice_mode(early), InvoiceMode.SMALL_AMOUNT_CANDIDATE)
        self.assertIs(invoice_mode(early), InvoiceMode.FULL)
        self.assertIs(invoice_mode(replace(early, gross_total="250.00", price_final=True)), InvoiceMode.SMALL_AMOUNT_CANDIDATE)
        self.assertIs(invoice_mode(replace(early, gross_total="250.01", price_final=True)), InvoiceMode.FULL)

    def test_early_offer_is_never_permitted_for_unknown_or_explicit_full_invoice(self):
        early = replace(self.facts, gross_total="200.00", price_final=False)
        for changes in ({"exception_3c": None}, {"exception_6a": True},
                        {"exception_13b": None}, {"german_rule_approved": False},
                        {"customer_requests_full": True}, {"currency": "USD"}):
            with self.subTest(changes=changes):
                self.assertIs(early_invoice_mode(replace(early, **changes)), InvoiceMode.FULL)

    def test_guest_decision_requires_both_checks(self):
        early = replace(self.facts, gross_total="200.00", price_final=False)
        final = replace(self.facts, gross_total="250.00", price_final=True)
        self.assertIs(guest_invoice_mode(early, final), InvoiceMode.SMALL_AMOUNT_CANDIDATE)
        self.assertIs(guest_invoice_mode(replace(early, gross_total="200.01"), final), InvoiceMode.FULL)
        self.assertIs(guest_invoice_mode(early, replace(final, gross_total="250.01")), InvoiceMode.FULL)
        self.assertIs(guest_invoice_mode(early, replace(final, price_final=False)), InvoiceMode.FULL)
        self.assertIs(guest_invoice_mode(early, replace(final, customer_requests_full=True)), InvoiceMode.FULL)

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
