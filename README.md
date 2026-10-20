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
  exceptions, unexpected recalculation and paid-invoice configuration are
  not comprehensively tested. Invoice legal compliance requires separate
  review for the actual business and event configuration.
* Docker packaging, operational installation and rollback instructions
  remain unfinished. No production installation is authorized by this file.
