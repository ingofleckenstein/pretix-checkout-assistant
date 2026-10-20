"""Add a notice only to explicitly enabled, eligible address-free invoices.

This does not make an invoice legally valid or enforce checkout eligibility.
Activation requires a separate event setting and a review of legal exceptions.
"""
from decimal import Decimal, InvalidOperation
from django.utils.translation import gettext

NOTICE = (
    'Small-amount invoice under Section 33 of the German VAT Implementing Regulation (UStDV).\n'
    'The recipient’s billing address is not required for this invoice.'
)


def add_small_invoice_notice(event, invoice):
    if not event.settings.get('checkout_assistant_small_invoice_notice', as_type=bool, default=False):
        return False
    if event.currency != 'EUR' or invoice.is_cancellation or invoice.reverse_charge:
        return False
    if invoice.order.customer_id or any((invoice.invoice_to_company, invoice.invoice_to_street,
                                         invoice.invoice_to_city, invoice.invoice_to_zipcode)):
        return False
    # A guest's contact name can appear without an address. Leave any other
    # unstructured recipient data alone.
    recipient = (invoice.invoice_to or '').strip()
    name = (invoice.invoice_to_name or '').strip()
    if recipient and recipient != name:
        return False
    try:
        total = Decimal(invoice.order.total)
        if not total.is_finite() or total <= 0 or total > Decimal('250.00'):
            return False
    except (InvalidOperation, ValueError, TypeError):
        return False
    # pretix calls this hook inside the invoice's selected language context.
    # pretix renders structured name fields instead of invoice_to when present.
    # Clear the invoice snapshot's name so the notice is rendered; the order's
    # contact details are not changed.
    invoice.invoice_to = gettext(NOTICE)
    invoice.invoice_to_name = ''
    invoice.save(update_fields=['invoice_to', 'invoice_to_name'])
    return True
