from decimal import Decimal
from types import SimpleNamespace as NS
import unittest

from pretix_checkout_assistant.automatic import should_attempt


class StoredAddresses:
    def __init__(self, addresses):
        self.addresses = addresses

    def all(self):
        return self.addresses


class AdapterTests(unittest.TestCase):
    def setUp(self):
        address = NS(name="Test Person", company="", street="Testweg 1",
                     zipcode="70176", city="Stuttgart", country="DE")
        self.customer = NS(pk=7, name="Test Person", email="test@example.org",
                           stored_addresses=StoredAddresses([address]))
        settings = NS(invoice_address_required=True, invoice_generate="True",
                      invoice_generate_only_business=False,
                      invoice_generate_sales_channels=["web"])
        self.request = NS(method="GET", GET={}, customer=self.customer,
                          event=NS(settings=settings), sales_channel=NS(identifier="web"))
        self.position = NS(attendee_name_parts=None)
        self.step = NS(cart_session={"customer_mode": "login", "customer": 7},
                       address_asked=True, get_cart=lambda: {"total": Decimal("20.00")},
                       order_questions_form=NS(fields={}),
                       contact_form=NS(fields={"email": object()}),
                       _positions_for_questions=[self.position],
                       forms=[NS(fields={"attendee_name_parts": object(), "save": object()})])

    def test_eligible_request_may_attempt_pretix_validation(self):
        self.assertTrue(should_attempt(self.request, self.step))

    def test_already_entered_or_untrusted_information_is_not_overwritten(self):
        for key, value in (("invoice_address", 99), ("widget_data", {"invoice-address-city": "Other"}),
                           ("customer", 8), ("customer_mode", "guest")):
            with self.subTest(key=key):
                original = self.step.cart_session.get(key)
                self.step.cart_session[key] = value
                self.assertFalse(should_attempt(self.request, self.step))
                if original is None:
                    self.step.cart_session.pop(key)
                else:
                    self.step.cart_session[key] = original

    def test_questions_and_extra_fields_stop_automatic_submission(self):
        self.step.order_questions_form.fields["question_1"] = object()
        self.assertFalse(should_attempt(self.request, self.step))
        self.step.order_questions_form.fields.clear()
        self.step.forms[0].fields["question_2"] = object()
        self.assertFalse(should_attempt(self.request, self.step))

    def test_invoice_setting_errors_and_backward_navigation_stop_it(self):
        self.request.GET["dir"] = "prev"
        self.assertFalse(should_attempt(self.request, self.step))
        self.request.GET.clear()
        self.request.event.settings.invoice_generate = "False"
        self.assertFalse(should_attempt(self.request, self.step))
        self.request.event.settings.invoice_generate = "True"
        self.step.get_cart = lambda: {"total": Decimal("0")}
        self.assertFalse(should_attempt(self.request, self.step))

    def test_multiple_profiles_or_tickets_do_not_choose_for_customer(self):
        self.customer.stored_addresses.addresses.append(self.customer.stored_addresses.addresses[0])
        self.assertFalse(should_attempt(self.request, self.step))
        self.customer.stored_addresses.addresses.pop()
        self.step._positions_for_questions.append(NS(attendee_name_parts=None))
        self.assertFalse(should_attempt(self.request, self.step))


if __name__ == "__main__":
    unittest.main()

