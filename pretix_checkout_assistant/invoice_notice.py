"""Add a notice only to explicitly enabled, eligible address-free invoices.

This does not make an invoice legally valid or enforce checkout eligibility.
Activation requires a separate event setting and a review of legal exceptions.
"""
from decimal import Decimal, InvalidOperation
from django.utils.translation import gettext, pgettext

NOTICE = (
    'Small-amount invoice under Section 33 of the German VAT Implementing Regulation (UStDV).\n'
    'The recipient’s billing address is not required for this invoice.'
)


def add_small_invoice_notice(event, invoice):
    if not event.settings.get('checkout_assistant_small_invoice_notice', as_type=bool, default=False):
        return False
    if event.currency != 'EUR' or invoice.is_cancellation or invoice.reverse_charge:
        return False
    customer = bool(invoice.order.customer_id)
    if customer:
        # Special-tax and electronic-routing cases keep all data.
        if not event.settings.get('checkout_assistant_german_small_invoice_approved', as_type=bool, default=False):
            return False
        if any((invoice.invoice_to_vat_id, invoice.invoice_to_beneficiary,
                invoice.internal_reference, invoice.custom_field)):
            return False
        if invoice.transmission_type != 'email':
            return False
        if any(rule and (rule.eu_reverse_charge or rule.custom_rules)
               for rule in [p.tax_rule for p in invoice.order.positions.select_related('tax_rule')]
               + [f.tax_rule for f in invoice.order.fees.select_related('tax_rule')]):
            return False
    elif any((invoice.invoice_to_company, invoice.invoice_to_street,
              invoice.invoice_to_city, invoice.invoice_to_zipcode)):
        return False
    # A guest's contact name can appear without an address. Leave any other
    # unstructured recipient data alone.
    recipient = (invoice.invoice_to or '').strip()
    name = (invoice.invoice_to_name or '').strip()
    if not customer and recipient and recipient != name:
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
    fields = ['invoice_to', 'invoice_to_name']
    if customer:
        for field in ('invoice_to_company', 'invoice_to_street', 'invoice_to_zipcode', 'invoice_to_city',
                      'invoice_to_state', 'invoice_to_country'):
            setattr(invoice, field, None)
            fields.append(field)
    invoice.save(update_fields=fields)
    # pretix can include participant names separately in each invoice line.
    # Remove the precise text it generated without touching product text or
    # the participant record on the order.
    for line in invoice.lines.all():
        if line.attendee_name:
            marker = '<br />' + pgettext('invoice', 'Attendee: {name}').format(name=line.attendee_name)
            line.description = line.description.replace(marker, '', 1)
            line.attendee_name = None
            line.save(update_fields=['description', 'attendee_name'])
    return True
