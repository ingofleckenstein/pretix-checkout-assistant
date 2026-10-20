"""Fail-closed decisions for an automatic customer checkout.

Not integrated into pretix. The future adapter must obtain these facts from
pretix's current request/cart, execute its regular validation and re-check
invoice generation after final ordering.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class CheckoutAction(Enum):
    SHOW_FORM = "show_form"
    APPLY_AND_VALIDATE = "apply_and_validate"


@dataclass(frozen=True)
class CheckoutFacts:
    authenticated_customer_id: Optional[int]
    cart_customer_id: Optional[int]
    customer_mode: str
    invoice_profiles: tuple
    existing_invoice_data: bool
    position_count: int
    individual_questions_exist: bool
    other_input_required: bool
    valid_customer_email: bool
    complete_customer_name: bool
    invoice_generation_enabled: bool
    backwards_navigation: bool
    previous_form_error: bool


def customer_checkout_action(facts: CheckoutFacts) -> CheckoutAction:
    """Return permission to attempt validation, never permission to skip it.

    Profiles must be the current customer's own; callers must ensure that
    invariant when querying. A single complete address and a single ticket
    avoids choosing on the customer's behalf or assigning another person's
    ticket. No profile updates are performed here.
    """
    if not facts.authenticated_customer_id or facts.cart_customer_id != facts.authenticated_customer_id:
        return CheckoutAction.SHOW_FORM
    if facts.customer_mode != "login" or facts.existing_invoice_data:
        return CheckoutAction.SHOW_FORM
    if facts.position_count != 1 or len(facts.invoice_profiles) != 1:
        return CheckoutAction.SHOW_FORM
    if (facts.individual_questions_exist is not False or facts.other_input_required is not False
            or facts.valid_customer_email is not True or facts.complete_customer_name is not True
            or facts.invoice_generation_enabled is not True or facts.backwards_navigation is not False
            or facts.previous_form_error is not False):
        return CheckoutAction.SHOW_FORM
    address = facts.invoice_profiles[0]
    if not isinstance(address, dict):
        return CheckoutAction.SHOW_FORM
    # A name or company is needed, as well as the complete postal address.
    for key in ("street", "zipcode", "city", "country"):
        if not isinstance(address.get(key), str) or not address[key].strip():
            return CheckoutAction.SHOW_FORM
    name, company = address.get("name"), address.get("company")
    if not any(isinstance(value, str) and value.strip() for value in (name, company)):
        return CheckoutAction.SHOW_FORM
    return CheckoutAction.APPLY_AND_VALIDATE
