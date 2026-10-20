# pretix-checkout-assistant

**Experimental prototype. Do not deploy or enable in production.**

Target under investigation: pretix 2026.8.0. This repository is an unfinished
prototype, not a release. The event flags for the guest experiment and invoice
notice are disabled by default.

For a narrowly defined signed-in customer case, the plugin fills a single
saved billing profile and attempts to submit pretix's normal information
form. It leaves the form visible when the data is ambiguous, extra answers
are needed or other safety checks fail. Saving a new profile uses pretix's
own unchecked consent checkbox. Keycloak integration is not verified.

The experimental guest flow uses a preliminary 200 EUR gross threshold
before payment and a final 250 EUR gross threshold including fees. If either
threshold is exceeded it asks for an address. An additional order-creation
guard rejects address-free orders that do not meet its checks. Events must
explicitly enable the experiment and attest that the simplified invoice is
legally eligible. This is not a complete automatic legal assessment.

The experimental guest adapter keeps pretix's event-wide billing address
settings enabled. For a guest request it hides the standard address panel
and uses the guest address steps; for a signed-in customer it leaves the
standard pretix form and saved-profile behavior in place. When returning
through the questions page, a guest address entered in a plugin step is
restored from the current cart session and tax is recalculated. Additional
participant questions still require normal pretix validation.

The guest experiment accepts both `invoice_generate=True` and `paid`.
Before invoice generation the plugin checks address-free guest orders again,
including the current total, position and fee tax rules. If the check fails,
invoice generation is rejected. pretix can still confirm the payment and record
an invoice generation error; staff must add a complete billing address and
then generate the invoice. The plugin registers a pretix notification type
for invoice generation failures. Each team member must explicitly enable this
notification in their personal pretix notification settings; delivery also
requires the normal notification worker, configured delivery method and order
read permission. This warns about any invoice failure, including failures not
caused by this plugin. It does not automatically repair an invoice. The
`checkout_assistant_guest_experiment`,
`checkout_assistant_german_small_invoice_approved`, and
`checkout_assistant_small_invoice_notice` settings are not yet exposed in a
control-panel form. Do not enable them on a live event without reviewing
invoicing, tax exceptions and all supported payment methods.

For events with the guest experiment enabled, a warning appears on the order
detail page and, with JavaScript enabled, on the customer and staff order
change forms whenever the order lacks a complete billing address. It does not
depend on the address printed on an earlier invoice. The warning does not
block changes. The previous private order-change monkeypatch was removed.
Checkout and invoice generation still enforce their own eligibility checks;
an invoice may therefore fail after a change or payment, and staff must
resolve it. The package remains pinned to pretix 2026.8.0 because other
checkout integration points also need compatibility testing. Installing with
`--no-deps` bypasses the package pin.

Plugin-provided checkout messages are available in German and English.
English is the source language. German translations are shipped as a compiled
Django catalog. Other languages have not been translated by this plugin.
The invoice notice follows the invoice language chosen by pretix (including
its event setting and, when configured, the customer's order language), not
the language of the staff member currently viewing it. Existing generated
invoices are not automatically regenerated.

An optional invoice hook adds a notice identifying an address-free guest
invoice as a Kleinbetragsrechnung. It is separately disabled by default.
Enabling this notice alone does not establish legal eligibility. The notice,
invoice settings and guest guard must be assessed together.

## Local tests

Tests used isolated pretix test events, test customers and fictitious
addresses. They did not touch the production installation:

* A signed-in native pretix customer with one ticket and one saved billing
  address reached payment automatically; a required participant question
  remained visible.
* A saved-address consent test covered both unchecked and checked states.
* A guest order of 200.01 EUR required an address before payment.
* Guest orders totaling 249 and exactly 250 EUR after payment fees generated
  invoices with the small-invoice notice.
* A guest order totaling 251 EUR after a test payment fee required an address
  and generated an invoice with that address.
* The guest address is displayed and editable on the review page. A local
  251 EUR test edited the address, returned to contact information, and
  completed an invoice with the edited address.
* A direct isolated guard test rejected a simulated 251 EUR address-free
  order and rolled back the database update. This is not a complete
  end-to-end test of late fee changes or interactions with other plugins.
* Request-scoped integration tests exercise genuine pretix flow objects with
  both guest and signed-in modes under the same required-address event
  settings, and check restoration of an entered guest address. These tests
  do not establish a new browser-to-invoice end-to-end result for that setup.
* An isolated, rolled-back test cloned a pending 249 EUR guest order, marked
  its bank-transfer payment confirmed without sending email, and verified that
  pretix generated the small-invoice notice with `invoice_generate=paid`.
  A changed 251 EUR order without an address failed invoice generation, while
  a 251 EUR order with an address generated an invoice. The test also confirmed
  that pretix retains payment confirmation when invoice generation fails.

Run local unit tests with Django installed:

```sh
python -m unittest discover -s tests -v
node tests/test_automatic_js.cjs
```

## Known blockers

* The address restoration stores a copy in the current cart session and
  recomputes tax when restoring it. Further integration tests are needed
  for address-dependent tax rules, cart changes and session backends.
* The final guard relies on an order signal inside pretix's transaction.
  Other receivers might have external effects; this needs a thorough
  integration review and testing before production use.
* Multiple tickets, addresses and complex participant forms need further
  design and tests. The automatic flow deliberately stops in uncertain cases.
* SEPA, real Keycloak/OIDC login, plugin combinations, sales channels, tax
  exceptions, unexpected recalculation and complete paid checkout flows are
  not comprehensively tested. Invoice legal compliance requires separate
  review for the actual business and event configuration.
* Docker packaging, operational installation and rollback instructions
  remain unfinished. No production installation is authorized by this file.
