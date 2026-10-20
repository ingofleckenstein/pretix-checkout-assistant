import logging

from django.dispatch import receiver
from django.templatetags.static import static
from django.utils.html import format_html
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from pretix.presale.signals import html_head, checkout_flow_steps, checkout_confirm_page_content
from pretix.presale.signals import order_info_top as presale_order_info_top
from pretix.control.signals import html_head as control_html_head, order_info as control_order_info
from pretix.multidomain.urlreverse import eventreverse
from pretix.base.signals import build_invoice_data, order_placed, register_notification_types
from pretix.base.notifications import ParametrizedOrderNotificationType
from pretix.base.models import InvoiceAddress
from pretix.base.services.orders import OrderError
from decimal import Decimal

from .automatic import should_attempt
from .invoice_notice import add_small_invoice_notice
from .guest_checkout import GuestQuestionsAdapter, GuestEarlyAddressStep, GuestFinalAddressStep, configured, enabled, address_complete, small_invoice_approved

logger = logging.getLogger(__name__)

ORDER_WARNING = gettext_lazy(
    'If you change this order and its total exceeds 250 EUR, a complete billing address may be required. '
    'Please add a billing address before changing the order.'
)


def order_needs_address_warning(event, order):
    if not configured(event):
        return False
    try:
        return not address_complete(order.invoice_address)
    except InvoiceAddress.DoesNotExist:
        return True


def order_warning_markup():
    return format_html('<div class="alert alert-warning" role="alert">{}</div>', ORDER_WARNING)


@receiver(presale_order_info_top, dispatch_uid='checkout_assistant_presale_order_warning')
@receiver(control_order_info, dispatch_uid='checkout_assistant_control_order_warning')
def order_address_warning(sender, order, request, **kwargs):
    return order_warning_markup() if order_needs_address_warning(sender, order) else ''


@receiver(html_head, dispatch_uid='checkout_assistant_presale_change_warning')
@receiver(control_html_head, dispatch_uid='checkout_assistant_control_change_warning')
def order_change_warning_script(sender, request, **kwargs):
    match = getattr(request, 'resolver_match', None)
    if not match or match.view_name not in ('presale:event.order.change', 'control:event.order.change'):
        return ''
    if not configured(sender):
        return ''
    query = {'code': match.kwargs.get('order' if match.view_name.startswith('presale:') else 'code')}
    if match.view_name.startswith('presale:'):
        query['secret'] = match.kwargs.get('secret')
    order = sender.orders.filter(**query).first()
    if not order or not order_needs_address_warning(sender, order):
        return ''
    try:
        src = static('pretix_checkout_assistant/automatic.js')
    except (ValueError, OSError):
        logger.exception('Checkout assistant warning script unavailable')
        return ''
    return format_html('<script defer data-order-address-warning="{}" src="{}"></script>', ORDER_WARNING, src)


@receiver(register_notification_types, dispatch_uid="checkout_assistant_invoice_failure_notification")
def invoice_failure_notification(sender, **kwargs):
    # pretix records this action after a failed invoice, even when payment
    # remains confirmed. Delivery uses each user's notification settings.
    return ParametrizedOrderNotificationType(
        sender,
        'pretix.event.order.invoice.failed',
        gettext_lazy('Invoice generation failed'),
        gettext_lazy('Invoice generation failed for order {order.code}. Check the order and create the invoice.'),
    )


@receiver(checkout_flow_steps, dispatch_uid="checkout_assistant_guest_questions_adapter")
def guest_questions_adapter(sender, **kwargs):
    return GuestQuestionsAdapter


@receiver(checkout_flow_steps, dispatch_uid="checkout_assistant_guest_early")
def guest_early_step(sender, **kwargs):
    return GuestEarlyAddressStep


@receiver(checkout_flow_steps, dispatch_uid="checkout_assistant_guest_final")
def guest_final_step(sender, **kwargs):
    return GuestFinalAddressStep


@receiver(checkout_confirm_page_content, dispatch_uid="checkout_assistant_guest_address_review")
def guest_address_review(sender, request, **kwargs):
    if not enabled(sender):
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
    if not configured(sender) or order.customer_id:
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
    total = order.total
    if (not small_invoice_approved(sender) or unsupported_tax or not positions or
            order.sales_channel.identifier not in sender.settings.invoice_generate_sales_channels or
            total <= 0 or total > Decimal('250.00')):
        raise OrderError(_('A complete billing address is required for this order. Please check your information.'))


@receiver(build_invoice_data, dispatch_uid="checkout_assistant_small_invoice_notice")
def invoice_notice(sender, invoice, **kwargs):
    # Orders can be modified after checkout. Recheck before a non-cancellation
    # invoice is committed, including when payment triggers delayed invoicing.
    if not invoice.is_cancellation:
        guest_final_guard(sender, invoice.order)
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
