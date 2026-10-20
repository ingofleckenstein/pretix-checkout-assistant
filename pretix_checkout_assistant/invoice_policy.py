"""Conservative policy gate for guest small-amount invoices.

This module is not integrated into pretix. Eligibility is a necessary gate,
not a substitute for validating invoice content or the final order.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum


class InvoiceMode(Enum):
    FULL = "full"
    SMALL_AMOUNT_CANDIDATE = "small_amount_candidate"


@dataclass(frozen=True)
class InvoiceFacts:
    gross_total: object
    currency: str
    price_final: bool
    german_rule_approved: bool
    exception_3c: bool | None
    exception_6a: bool | None
    exception_13b: bool | None
    customer_requests_full: bool


def invoice_mode(facts: InvoiceFacts) -> InvoiceMode:
    """Only permit the short invoice path when every prerequisite is explicit.

    Re-run on final order total after fees, discounts and tax recalculation.
    A candidate must still be checked for all required invoice content and
    any further applicable rules. Unknown legal facts fail closed.
    """
    if facts.customer_requests_full is not False:
        return InvoiceMode.FULL
    if facts.price_final is not True or facts.german_rule_approved is not True:
        return InvoiceMode.FULL
    if facts.currency != "EUR":
        return InvoiceMode.FULL
    if any(flag is not False for flag in (facts.exception_3c, facts.exception_6a, facts.exception_13b)):
        return InvoiceMode.FULL
    try:
        if isinstance(facts.gross_total, (float, bool)):
            return InvoiceMode.FULL
        total = Decimal(facts.gross_total)
        if not total.is_finite() or total <= 0 or total > Decimal("250.00"):
            return InvoiceMode.FULL
        if total != total.quantize(Decimal("0.01")):
            return InvoiceMode.FULL
    except (InvalidOperation, ValueError, TypeError):
        return InvoiceMode.FULL
    return InvoiceMode.SMALL_AMOUNT_CANDIDATE

