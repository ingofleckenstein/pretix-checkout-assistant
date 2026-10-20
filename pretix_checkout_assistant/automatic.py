"""Experimental conservative integration for pretix 2026.8.

Not production-ready: guest checkout, invoices and end-to-end tests remain open.
"""
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from .customer_policy import CheckoutAction, CheckoutFacts, customer_checkout_action


def should_attempt(request, step, *, prefill_only=False):
    """Allow the browser to submit the normal pretix form only in a narrow case."""
    if request.method != "GET" or request.GET.get("dir") == "prev":
        return False
    if getattr(request, "pci_dss_payment_page", False):
        return False
    customer = getattr(request, "customer", None)
    session = step.cart_session
    if not customer or session.get("customer_mode") != "login":
        return False
    if session.get("customer") != customer.pk or session.get("invoice_address"):
        return False
    if any(k.startswith("invoice-address-") for k in session.get("widget_data", {})):
        return False
    event = request.event
    if not step.address_asked or not event.settings.invoice_address_required:
        return False
    if event.settings.invoice_generate not in ("True", "paid"):
        return False
    if event.settings.invoice_generate_only_business:
        return False
    if request.sales_channel.identifier not in event.settings.invoice_generate_sales_channels:
        return False
    if step.get_cart()["total"] <= 0:
        return False
    if not prefill_only and step.order_questions_form and step.order_questions_form.fields:
        return False
    # pretix itself prepopulates the customer's telephone number. Its normal
    # form validation still decides whether a required number is present.
    if set(step.contact_form.fields) - {"email", "email_repeat", "phone"}:
        return False
    positions = step._positions_for_questions
    if not positions or len(step.forms) != len(positions):
        return False
    if not prefill_only and len(positions) != 1:
        return False
    form = step.forms[0]
    if not prefill_only:
        if set(form.fields) - {"attendee_name_parts", "attendee_email", "save", "saved_id"}:
            return False
        # An optional attendee email may be left blank; a required one is a
        # deliberate attendee input and must not be silently guessed.
        attendee_email = form.fields.get("attendee_email")
        if attendee_email is not None and getattr(attendee_email, "required", True):
            return False
    if "attendee_name_parts" not in form.fields:
        return False
    if positions[0].attendee_name_parts:
        return False
    try:
        validate_email(customer.email)
    except (ValidationError, TypeError):
        return False
    profiles = list(customer.stored_addresses.all()[:2])
    addresses = tuple({
        "name": a.name,
        "company": a.company,
        "street": a.street,
        "zipcode": a.zipcode,
        "city": a.city,
        "country": str(a.country or ""),
    } for a in profiles)
    facts = CheckoutFacts(
        authenticated_customer_id=customer.pk,
        cart_customer_id=session.get("customer"),
        customer_mode=session.get("customer_mode"),
        invoice_profiles=addresses,
        existing_invoice_data=False,
        # Prefill only applies the billing profile; it never submits or fills
        # the names of additional attendees. Submission remains single-ticket.
        position_count=1 if prefill_only else len(positions),
        individual_questions_exist=False,
        other_input_required=False,
        valid_customer_email=True,
        complete_customer_name=bool(customer.name),
        invoice_generation_enabled=True,
        backwards_navigation=False,
        previous_form_error=False,
    )
    return customer_checkout_action(facts) is CheckoutAction.APPLY_AND_VALIDATE
