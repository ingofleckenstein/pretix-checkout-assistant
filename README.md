# pretix-checkout-assistant

**Work in progress: this is not an installable pretix plugin. Do not deploy it.**

Target for development: pretix 2026.8.0; compatibility with the installed customer OIDC and Keycloak membership plugins must be verified in an isolated environment.

## Current contents

Two independent, experimental decision modules and unit tests. They do not read pretix data, alter checkout, generate invoices, or determine legal compliance. Callers must obtain and verify their inputs and perform pretix's own validation.

- `customer_policy` permits attempting normal validation only for a conservative, unambiguous customer scenario.
- `invoice_policy` identifies potential small-invoice candidates only when explicitly confirmed prerequisites are met; unknowns fall back to a full invoice.

Run the current unit tests from the repository root:

```sh
python -m unittest discover -s tests -v
```

## Outstanding work

Pretix integration and end-to-end checkout tests, profile selection and consent, the guest checkout choices, tax and price recalculation, final invoice generation and PDF verification, exception handling, version compatibility, and installation and rollback instructions are not implemented. All of these are required before a release.
