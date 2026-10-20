import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

from pretix_checkout_assistant.invoice_notice import NOTICE, add_small_invoice_notice


def sample(enabled=True):
    settings = Mock()
    settings.get.return_value = enabled
    event = SimpleNamespace(currency='EUR', settings=settings)
    queryset = SimpleNamespace(select_related=lambda *args: [])
    invoice = SimpleNamespace(is_cancellation=False, reverse_charge=False,
        order=SimpleNamespace(customer_id=None, total=Decimal('250.00'), positions=queryset, fees=queryset),
        invoice_to='', invoice_to_name='', invoice_to_company='', invoice_to_street='',
        invoice_to_city='', invoice_to_zipcode='', invoice_to_state='', invoice_to_country='DE',
        invoice_to_is_business=False, invoice_to_vat_id='', invoice_to_beneficiary='',
        internal_reference='', custom_field='', transmission_type='email', save=Mock(),
        lines=SimpleNamespace(all=lambda: []))
    return event, invoice


class InvoiceNoticeTests(unittest.TestCase):
    def test_small_guest_invoice(self):
        event, invoice = sample()
        with patch('pretix_checkout_assistant.invoice_notice.gettext', return_value=NOTICE):
            self.assertTrue(add_small_invoice_notice(event, invoice))
        self.assertEqual(invoice.invoice_to, NOTICE)
        invoice.save.assert_called_once_with(update_fields=['invoice_to', 'invoice_to_name'])

    def test_guest_name_without_address_is_replaced_by_notice(self):
        event, invoice = sample()
        invoice.invoice_to = invoice.invoice_to_name = 'Test Gast'
        with patch('pretix_checkout_assistant.invoice_notice.gettext', return_value=NOTICE):
            self.assertTrue(add_small_invoice_notice(event, invoice))
        self.assertEqual(invoice.invoice_to, NOTICE)
        self.assertEqual(invoice.invoice_to_name, '')

    def test_unstructured_recipient_is_not_overwritten(self):
        event, invoice = sample()
        invoice.invoice_to_name = 'Test Gast'
        invoice.invoice_to = 'Test Gast\nTeststrasse 1'
        self.assertFalse(add_small_invoice_notice(event, invoice))
        invoice.save.assert_not_called()

    def test_disabled_by_default_or_ineligible(self):
        event, invoice = sample(False)
        self.assertFalse(add_small_invoice_notice(event, invoice))
        for field, value in [('is_cancellation', True), ('reverse_charge', True),
                             ('invoice_to_company', 'Test'), ('invoice_to_street', 'Test')]:
            event, invoice = sample()
            setattr(invoice, field, value)
            self.assertFalse(add_small_invoice_notice(event, invoice), field)
        for field, value in [('total', Decimal('250.01')),
                             ('total', Decimal('0.00'))]:
            event, invoice = sample()
            setattr(invoice.order, field, value)
            self.assertFalse(add_small_invoice_notice(event, invoice), field)
        event, invoice = sample()
        event.currency = 'USD'
        self.assertFalse(add_small_invoice_notice(event, invoice))

    def test_registered_customer_receives_anonymous_invoice(self):
        event, invoice = sample()
        invoice.order.customer_id = 3
        invoice.invoice_to_name = 'Customer'
        invoice.invoice_to = 'Customer\nStreet 1\n12345 City'
        invoice.invoice_to_street = 'Street 1'
        invoice.invoice_to_city = 'City'
        invoice.invoice_to_zipcode = '12345'
        with patch('pretix_checkout_assistant.invoice_notice.gettext', return_value=NOTICE):
            self.assertTrue(add_small_invoice_notice(event, invoice))
        self.assertEqual(invoice.invoice_to, NOTICE)
        self.assertEqual(invoice.invoice_to_name, '')
        self.assertIsNone(invoice.invoice_to_street)
        self.assertIsNone(invoice.invoice_to_country)

    def test_registered_special_cases_are_not_anonymized(self):
        for field, value in [('invoice_to_vat_id', 'DE1'),
                             ('transmission_type', 'peppol'), ('internal_reference', 'reference')]:
            event, invoice = sample()
            invoice.order.customer_id = 3
            setattr(invoice, field, value)
            self.assertFalse(add_small_invoice_notice(event, invoice), field)
            invoice.save.assert_not_called()

    def test_registered_business_without_special_tax_is_anonymized(self):
        event, invoice = sample()
        invoice.order.customer_id = 3
        invoice.invoice_to_is_business = True
        invoice.invoice_to_company = 'Example company'
        invoice.invoice_to_name = 'Example person'
        self.assertTrue(add_small_invoice_notice(event, invoice))
        self.assertIsNone(invoice.invoice_to_company)
        self.assertEqual(invoice.invoice_to_name, '')

    def test_attendee_name_is_removed_from_invoice_line(self):
        event, invoice = sample()
        invoice.order.customer_id = 3
        line = SimpleNamespace(description='Ticket<br />Attendee: Test Person',
                               attendee_name='Test Person', save=Mock())
        invoice.lines = SimpleNamespace(all=lambda: [line])
        with patch('pretix_checkout_assistant.invoice_notice.pgettext', return_value='Attendee: {name}'):
            self.assertTrue(add_small_invoice_notice(event, invoice))
        self.assertEqual(line.description, 'Ticket')
        self.assertIsNone(line.attendee_name)
