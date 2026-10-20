import logging

from django.dispatch import receiver
from django.templatetags.static import static
from django.utils.html import format_html
from django.utils.translation import gettext as _
from pretix.presale.signals import html_head, checkout_flow_steps, checkout_confirm_page_content
from pretix.multidomain.urlreverse import eventreverse
from pretix.base.signals import build_invoice_data, order_placed
from pretix.base.models import InvoiceAddress, OrderFee
from pretix.base.services.orders import OrderError
from decimal import Decimal

from .automatic import should_attempt
from .invoice_notice import add_small_invoice_notice
from .guest_checkout import GuestEarlyAddressStep, GuestFinalAddressStep, enabled, address_complete, small_invoice_approved

logger = logging.getLogger(__name__)


@receiver(checkout_flow_steps, dispatch_uid="checkout_assistant_guest_early")
def guest_early_step(sender, **kwargs):
    return GuestEarlyAddressStep


@receiver(checkout_flow_steps, dispatch_uid="checkout_assistant_guest_final")
def guest_final_step(sender, **kwargs):
    return GuestFinalAddressStep


@receiver(checkout_confirm_page_content, dispatch_uid="checkout_assistant_guest_address_review")
def guest_address_review(sender, request, **kwargs):
    if not enabled(sender) or sender.settings.invoice_address_asked:
        return ""
    step = next((s for s in getattr(request, '_checkout_flow', ())
                 if s.identifier == 'checkout_assistant_address_final'), None)
    if not step:
        return ""
    step.request = request
    if step.cart_customer or not address_complete(step.invoice_address):
        return ""
    addr = step.invoice_address
    url_kwargs = {'step': step.identifier}
    namespace = request.resolver_match.kwargs.get('cart_namespace')
    if namespace:
        url_kwargs['cart_namespace'] = namespace
    url = eventreverse(sender, 'presale:event.checkout', kwargs=url_kwargs) + '?edit_invoice=1'
    return format_html(
        '<div class="panel panel-default"><div class="panel-heading">'
        '<h3 class="panel-title">{} '
        '<a href="{}">{}</a></h3></div><div class="panel-body">'
        '<div>{}</div><div>{}</div><div>{}</div><div>{} {}</div><div>{}</div>'
        '</div></div>', _('Billing address'), url, _('Edit'), addr.company, addr.name, addr.street,
        addr.zipcode, addr.city, addr.country.name if addr.country else ''
    )


@receiver(order_placed, dispatch_uid="checkout_assistant_guest_final_guard")
def guest_final_guard(sender, order, **kwargs):
    """Recheck after pretix calculates final fees, within order creation's transaction."""
    if not enabled(sender) or order.customer_id:
        return
    if order.total == Decimal('0.00'):
        return
    try:
        address = order.invoice_address
    except InvoiceAddress.DoesNotExist:
        address = None
    if address_complete(address):
        return
    positions = list(order.positions.select_related('tax_rule'))
    fees = list(order.fees.select_related('tax_rule'))
    unsupported_tax = any(rule and (rule.eu_reverse_charge or rule.custom_rules)
                          for rule in [p.tax_rule for p in positions] + [f.tax_rule for f in fees])
    preliminary = sum((p.price for p in positions), Decimal('0.00')) + sum(
        (f.value for f in fees if f.fee_type != OrderFee.FEE_TYPE_PAYMENT), Decimal('0.00'))
    total = order.total
    if (not small_invoice_approved(sender) or unsupported_tax or not positions or
            order.sales_channel.identifier not in sender.settings.invoice_generate_sales_channels or
            preliminary <= 0 or preliminary > Decimal('200.00') or
            total <= 0 or total > Decimal('250.00')):
        raise OrderError(_('A complete billing address is required for this order. Please check your information.'))


@receiver(build_invoice_data, dispatch_uid="checkout_assistant_small_invoice_notice")
def invoice_notice(sender, invoice, **kwargs):
    add_small_invoice_notice(sender, invoice)


@receiver(html_head, dispatch_uid="checkout_assistant_experimental_head")
def checkout_head(sender, request, **kwargs):
    match = getattr(request, "resolver_match", None)
    if not match or match.kwargs.get("step") != "questions":
        return ""
    step = next((s for s in getattr(request, "_checkout_flow", ()) if s.identifier == "questions"), None)
    if not step:
        return ""
    try:
        eligible = should_attempt(request, step)
        prefill = eligible or should_attempt(request, step, prefill_only=True)
    except Exception:
        # A compatibility problem must leave the standard checkout available.
        logger.exception("Checkout assistant eligibility check failed")
        return ""
    if not prefill:
        return ""
    try:
        script_url = static("pretix_checkout_assistant/automatic.js")
    except (ValueError, OSError):
        logger.exception("Checkout assistant static file unavailable")
        return ""
    return format_html('<script defer data-checkout-assistant="{}" src="{}"></script>',
                       "submit" if eligible else "prefill", script_url)
