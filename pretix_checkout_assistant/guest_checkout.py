"""Experimental guest address steps. Disabled by default, not production-ready."""
from decimal import Decimal

from django.contrib import messages
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from pretix.base.models import InvoiceAddress, TaxRule
from pretix.base.services.cart import CartManager
from pretix.presale.checkoutflow import TemplateFlowStep
from pretix.presale.forms.checkout import InvoiceAddressForm
from pretix.presale.views import CartMixin
from pretix.presale.views.cart import get_or_create_cart_id
from pretix.helpers.http import redirect_to_url
from django_scopes import scopes_disabled
from .fee_limits import early_limit


# Keep the copy only in the current cart session. pretix removes the original
# address when its questions form is submitted with invoice_address_asked off.
BACKUP_KEY = 'checkout_assistant_guest_address'
ADDRESS_FIELDS = (
    'is_business', 'company', 'name_parts', 'street', 'zipcode', 'city',
    'country_old', 'country', 'state', 'vat_id', 'vat_id_validated',
    'custom_field', 'internal_reference', 'beneficiary', 'transmission_type',
    'transmission_info',
)


def save_address_backup(cart_session, address):
    data = {field: getattr(address, field) for field in ADDRESS_FIELDS}
    data['country'] = address.country.code if address.country else ''
    cart_session[BACKUP_KEY] = data


def restore_address_backup(step):
    data = step.cart_session.get(BACKUP_KEY)
    if not isinstance(data, dict) or address_complete(step.invoice_address):
        return
    values = {field: data[field] for field in ADDRESS_FIELDS if field in data}
    with scopes_disabled():
        address = step.invoice_address
        for field, value in values.items():
            setattr(address, field, value)
        address.save()
    try:
        CartManager(event=step.event, cart_id=get_or_create_cart_id(step.request),
                    invoice_address=address,
                    sales_channel=step.request.sales_channel).recompute_final_prices_and_taxes()
    except TaxRule.SaleNotAllowed:
        with scopes_disabled():
            address.delete()
        step.cart_session.pop(BACKUP_KEY, None)
        step.cart_session.pop('invoice_address', None)
        empty = InvoiceAddress()
        step.request._checkout_flow_invoice_address = empty
        step.__dict__['invoice_address'] = empty
        messages.error(step.request, _('Unfortunately, this address cannot be used for this order.'))
        return
    step.cart_session['invoice_address'] = address.pk
    step.request._checkout_flow_invoice_address = address
    # cached_property may have cached the empty instance on this step.
    step.__dict__['invoice_address'] = address


def configured(event):
    return event.settings.get('checkout_assistant_guest_experiment', as_type=bool, default=False)


def enabled(event):
    return configured(event)


def small_invoice_approved(event):
    return (event.currency == 'EUR'
            and event.settings.get('checkout_assistant_german_small_invoice_approved', as_type=bool, default=False)
            and event.settings.invoice_generate in ('True', 'paid')
            and not event.settings.invoice_generate_only_business)


def address_complete(address):
    return bool(address and address.pk and address.street and address.zipcode and address.city
                and address.country and (address.name or address.company))


class GuestQuestionsAdapter(CartMixin, TemplateFlowStep):
    """Select the guest form for this request without changing event settings."""
    priority = 49
    identifier = 'checkout_assistant_guest_questions_adapter'

    def is_applicable(self, request):
        self.request = request
        if enabled(self.event) and self.cart_session.get('customer_mode', 'guest') == 'guest':
            for step in getattr(request, '_checkout_flow', ()):
                if step.identifier in ('questions', 'confirm'):
                    step.__dict__['address_asked'] = False
        return False


class RequiredAddressForm(InvoiceAddressForm):
    @property
    def address_required(self):
        return True

    def clean(self):
        data = super().clean() or self.cleaned_data
        for key in ('street', 'zipcode', 'city', 'country'):
            if not data.get(key):
                self.add_error(key, _('This field is required.'))
        return data


class GuestAddressStep(CartMixin, TemplateFlowStep):
    template_name = 'pretix_checkout_assistant/guest_address.html'
    label = _('Invoice address')
    icon = 'address-card'
    final = False

    def is_applicable(self, request):
        self.request = request
        if not enabled(self.event) or self.cart_customer:
            return False
        restore_address_backup(self)
        match = getattr(request, 'resolver_match', None)
        editing = (match and match.kwargs.get('step') == self.identifier
                   and request.GET.get('edit_invoice') == '1')
        if editing and address_complete(self.invoice_address):
            return True
        if address_complete(self.invoice_address):
            return False
        if not small_invoice_approved(self.event):
            return True
        if request.sales_channel.identifier not in self.event.settings.invoice_generate_sales_channels:
            return True
        if any(p.item.tax_rule and (p.item.tax_rule.eu_reverse_charge or p.item.tax_rule.custom_rules)
               for p in self.positions):
            return True
        try:
            cart = self.get_cart(payments=None if self.final else [])
            return Decimal(cart['total']) > (Decimal('250.00') if self.final else early_limit(self.event))
        except (KeyError, ValueError, TypeError, TaxRule.SaleNotAllowed):
            return True

    def is_completed(self, request, warn=False):
        self.request = request
        return address_complete(self.invoice_address)

    @cached_property
    def form(self):
        return RequiredAddressForm(data=self.request.POST if self.request.method == 'POST' else None,
                                   event=self.event, request=self.request,
                                   instance=self.invoice_address, validate_vat_id=True)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['form'] = self.form
        ctx['cart'] = self.get_cart()
        ctx['cart_session'] = self.cart_session
        return ctx

    def post(self, request):
        self.request = request
        if not self.form.is_valid():
            return self.render()
        address = self.form.save()
        try:
            CartManager(event=self.event, cart_id=get_or_create_cart_id(request),
                        invoice_address=address, sales_channel=request.sales_channel).recompute_final_prices_and_taxes()
        except TaxRule.SaleNotAllowed:
            messages.error(request, _('Unfortunately, this address cannot be used for this order.'))
            return self.render()
        self.cart_session['invoice_address'] = address.pk
        save_address_backup(self.cart_session, address)
        return redirect_to_url(self.get_next_url(request))


class GuestEarlyAddressStep(GuestAddressStep):
    priority = 100
    identifier = 'checkout_assistant_address_early'


class GuestFinalAddressStep(GuestAddressStep):
    priority = 300
    identifier = 'checkout_assistant_address_final'
    final = True
