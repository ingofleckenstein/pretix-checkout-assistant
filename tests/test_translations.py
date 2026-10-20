import gettext
import unittest
from pathlib import Path

from pretix_checkout_assistant.invoice_notice import NOTICE


class TranslationCatalogTests(unittest.TestCase):
    def test_compiled_german_catalog_contains_checkout_and_invoice_texts(self):
        catalog = Path(__file__).resolve().parents[1] / 'pretix_checkout_assistant' / 'locale' / 'de' / 'LC_MESSAGES' / 'django.mo'
        with catalog.open('rb') as source:
            german = gettext.GNUTranslations(source)
        for msgid, expected in [
            ('A complete billing address is required for this order.', 'Für diese Bestellung'),
            ('Billing address', 'Rechnungsanschrift'),
            ('Edit', 'Bearbeiten'),
            (NOTICE, 'Kleinbetragsrechnung gemäß § 33 UStDV.'),
        ]:
            self.assertIn(expected, german.gettext(msgid))


if __name__ == '__main__':
    unittest.main()
