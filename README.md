# pretix-checkout-assistant

**Experimental work in progress. Do not install or deploy in production.**

Target: pretix 2026.8.0. This is a partial pretix plugin, not a release.

For a narrow signed-in customer scenario, the adapter tries to populate one saved billing profile and submit the normal pretix form. It refuses automatic submission for multiple tickets or addresses, existing invoice data, individual questions, unknown inputs or unsuitable invoice settings. Pretix must still perform its own validation and tax calculation.

One isolated local test with a native pretix customer, one paid ticket, one saved address and bank transfer reached payment automatically and produced an invoice PDF containing the saved address. A second local test left a required participant question visible and blocked progression until it was answered. These are limited scenarios, not a production qualification. A real Keycloak login, guest checkout, changes to totals, Docker deployment and the remaining edge cases have not been tested end to end.

Pretix's existing address-save checkbox is initially unchecked; the prototype does not select it. A first-time address and consent flow still needs end-to-end testing.

Guest checkout choices, small-amount invoices, comprehensive invoice-generation handling, and production installation and rollback instructions are not implemented. The small-invoice policy is not wired into checkout. Do not relax the event's address requirement in anticipation of this feature.

Run the unit tests in an environment with Django installed:

```sh
python -m unittest discover -s tests -v
node tests/test_automatic_js.cjs
```

The small-invoice module identifies potential candidates only when prerequisites are explicitly confirmed. Unknown cases fall back to a full invoice; this does not determine legal compliance.
