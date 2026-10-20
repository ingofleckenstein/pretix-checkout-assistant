from dataclasses import replace
import unittest
from pretix_checkout_assistant.customer_policy import CheckoutAction, CheckoutFacts, customer_checkout_action


class CustomerPolicyTests(unittest.TestCase):
    def setUp(self):
        self.address = {"name": "A Person", "company": "", "street": "Example 1",
                        "zipcode": "12345", "city": "Example", "country": "DE"}
        self.base = CheckoutFacts(authenticated_customer_id=1, cart_customer_id=1,
            customer_mode="login", invoice_profiles=(self.address,), existing_invoice_data=False,
            position_count=1, individual_questions_exist=False, other_input_required=False,
            valid_customer_email=True, complete_customer_name=True,
            invoice_generation_enabled=True, backwards_navigation=False, previous_form_error=False)

    def test_complete_customer_can_attempt_validation(self):
        self.assertIs(customer_checkout_action(self.base), CheckoutAction.APPLY_AND_VALIDATE)

    def test_ambiguous_or_untrusted_context_always_shows_form(self):
        cases = [dict(authenticated_customer_id=None), dict(cart_customer_id=2),
                 dict(customer_mode="guest"), dict(invoice_profiles=()),
                 dict(invoice_profiles=(self.address, self.address)), dict(existing_invoice_data=True),
                 dict(position_count=2), dict(individual_questions_exist=True),
                 dict(individual_questions_exist=None), dict(other_input_required=True),
                 dict(valid_customer_email=False), dict(complete_customer_name=False),
                 dict(invoice_generation_enabled=False), dict(backwards_navigation=True),
                 dict(previous_form_error=True)]
        for case in cases:
            with self.subTest(case=case):
                self.assertIs(customer_checkout_action(replace(self.base, **case)), CheckoutAction.SHOW_FORM)

    def test_incomplete_address_always_shows_form(self):
        for field in ("name", "street", "zipcode", "city", "country"):
            with self.subTest(field=field):
                address = dict(self.address, **{field: " "})
                self.assertIs(customer_checkout_action(replace(self.base, invoice_profiles=(address,))),
                              CheckoutAction.SHOW_FORM)

    def test_business_can_use_company_name(self):
        address = dict(self.address, name="", company="Example GmbH")
        self.assertIs(customer_checkout_action(replace(self.base, invoice_profiles=(address,))),
                      CheckoutAction.APPLY_AND_VALIDATE)


if __name__ == "__main__":
    unittest.main()
