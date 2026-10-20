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


FINAL_GROSS_LIMIT = Decimal("250.00")


def _candidate(facts: InvoiceFacts, limit: Decimal) -> InvoiceMode:
    if facts.customer_requests_full is not False:
        return InvoiceMode.FULL
    if facts.german_rule_approved is not True:
        return InvoiceMode.FULL
    if facts.currency != "EUR":
        return InvoiceMode.FULL
    if any(flag is not False for flag in (facts.exception_3c, facts.exception_6a, facts.exception_13b)):
        return InvoiceMode.FULL
    try:
        if isinstance(facts.gross_total, (float, bool)):
            return InvoiceMode.FULL
        total = Decimal(facts.gross_total)
        if not total.is_finite() or total <= 0 or total > limit:
            return InvoiceMode.FULL
        if total != total.quantize(Decimal("0.01")):
            return InvoiceMode.FULL
    except (InvalidOperation, ValueError, TypeError):
        return InvoiceMode.FULL
    return InvoiceMode.SMALL_AMOUNT_CANDIDATE


def early_invoice_mode(facts: InvoiceFacts, early_limit: Decimal = Decimal('0.00')) -> InvoiceMode:
    """Preliminary offer only; never authorizes an address-free order.

    The amount must include every known gross component at this stage. A
    separate final check is mandatory even when the early result is eligible.
    """
    return _candidate(facts, min(FINAL_GROSS_LIMIT, early_limit))


def invoice_mode(facts: InvoiceFacts) -> InvoiceMode:
    """Evaluate the final gross total, including fees, rounding and taxes.

    A candidate still requires legal and invoice-content validation. Unknown
    facts fail closed; this helper alone cannot enforce checkout safety.
    """
    if facts.price_final is not True:
        return InvoiceMode.FULL
    return _candidate(facts, FINAL_GROSS_LIMIT)


def guest_invoice_mode(early: InvoiceFacts, final: InvoiceFacts, early_limit: Decimal = Decimal('0.00')) -> InvoiceMode:
    """Require both the preliminary buffer and the final legal limit.

    This is still only a policy decision: the caller must obtain both totals
    from the same checkout and enforce the result before placing an order.
    """
    if early_invoice_mode(early, early_limit) is not InvoiceMode.SMALL_AMOUNT_CANDIDATE:
        return InvoiceMode.FULL
    return invoice_mode(final)
