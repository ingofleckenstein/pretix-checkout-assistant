import unittest
from decimal import Decimal
from types import SimpleNamespace

from pretix.base.payment import BasePaymentProvider
from pretix_checkout_assistant.fee_limits import early_limit


class FakeProvider(BasePaymentProvider):
    @property
    def is_enabled(self):
        return True

    def __init__(self, absolute, percent, reverse=False):
        self.event = SimpleNamespace(currency='EUR')
        self.settings = SimpleNamespace(get=lambda key, **kw: {
            '_fee_abs': Decimal(absolute), '_fee_percent': Decimal(percent),
            '_fee_reverse_calc': reverse,
        }[key])


def event(*providers):
    return SimpleNamespace(get_payment_providers=lambda cached: dict(enumerate(providers)))


class FeeLimitTests(unittest.TestCase):
    def test_no_fee_and_fixed_fee(self):
        self.assertEqual(early_limit(event(FakeProvider('0', '0'))), Decimal('250.00'))
        self.assertEqual(early_limit(event(FakeProvider('2', '0'))), Decimal('248.00'))

    def test_largest_fee_and_percentage_are_bounded_at_250(self):
        self.assertEqual(early_limit(event(FakeProvider('2', '0'), FakeProvider('1', '2'))), Decimal('244.00'))

    def test_unknown_provider_fails_closed(self):
        class Custom(FakeProvider):
            def calculate_fee(self, price):
                return Decimal('0')
        self.assertEqual(early_limit(event(Custom('0', '0'))), Decimal('0.00'))
