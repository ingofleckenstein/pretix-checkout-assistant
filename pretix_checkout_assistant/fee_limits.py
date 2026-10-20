"""Conservative early limit based on enabled payment providers."""
import logging
from decimal import Decimal

from pretix.base.payment import BasePaymentProvider, GiftCardPayment

LEGAL_LIMIT = Decimal('250.00')
logger = logging.getLogger(__name__)


def early_limit(event):
    """Bound fees at 250 EUR; unknown provider behavior requires an address."""
    try:
        maximum = Decimal('0.00')
        for provider in event.get_payment_providers(cached=True).values():
            if not provider.is_enabled:
                continue
            # pretix registers this provider as enabled even when the
            # organizer has no gift cards and it cannot be selected.
            if isinstance(provider, GiftCardPayment) and not event.organizer.has_gift_cards:
                continue
            if (type(provider).calculate_fee is not BasePaymentProvider.calculate_fee
                    or provider.multi_use_supported):
                return Decimal('0.00')
            absolute = provider.settings.get('_fee_abs', as_type=Decimal, default=0)
            percent = provider.settings.get('_fee_percent', as_type=Decimal, default=0)
            absolute, percent = Decimal(absolute), Decimal(percent)
            if (not absolute.is_finite() or not percent.is_finite()
                    or absolute < 0 or percent < 0 or percent >= 100):
                return Decimal('0.00')
            fee = provider.calculate_fee(LEGAL_LIMIT)
            if not fee.is_finite() or fee < 0:
                return Decimal('0.00')
            maximum = max(maximum, fee)
        return max(Decimal('0.00'), LEGAL_LIMIT - maximum)
    except Exception:
        logger.exception('Could not determine a safe payment fee limit')
        return Decimal('0.00')
