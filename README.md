# pretix-checkout-assistant

**Experimental work in progress. Do not install or deploy in production.**

Target: pretix 2026.8.0. The repository now contains an experimental, partial pretix plugin. It is not a release and has not passed end-to-end checkout, invoice PDF, Docker, or Keycloak tests.

For a deliberately narrow signed-in customer scenario, the experimental adapter tries to populate a single saved billing profile and submit the normal pretix form. It refuses automatic submission for multiple tickets or addresses, existing invoice data, individual questions, unknown inputs, or unsuitable invoice settings. Pretix must still perform its own validation and tax calculation. This behavior needs integration testing.

Guest checkout choices, small-amount invoices, robust invoice-generation handling, consent flow improvements and production installation and rollback instructions are **not implemented**.

To run the current unit tests in an environment with Django installed:

```sh
python -m unittest discover -s tests -v
```

The small-invoice module only identifies potential candidates when explicitly confirmed prerequisites are met; unknown cases fall back to a full invoice. It does not determine legal compliance.
