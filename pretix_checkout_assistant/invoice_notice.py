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
    if invoice.order.customer_id or any((invoice.invoice_to, invoice.invoice_to_name,
                                         invoice.invoice_to_company, invoice.invoice_to_street,
                                         invoice.invoice_to_city, invoice.invoice_to_zipcode)):
        return False
    try:
        total = Decimal(invoice.order.total)
        if not total.is_finite() or total <= 0 or total > Decimal('250.00'):
            return False
    except (InvalidOperation, ValueError, TypeError):
        return False
    # pretix calls this hook inside the invoice's selected language context.
    invoice.invoice_to = gettext(NOTICE)
    invoice.save(update_fields=['invoice_to'])
    return True
