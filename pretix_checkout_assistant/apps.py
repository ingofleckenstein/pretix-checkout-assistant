from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class CheckoutAssistantApp(AppConfig):
    name = "pretix_checkout_assistant"
    verbose_name = _("Checkout Assistant (experimental)")

    class PretixPluginMeta:
        name = _("Checkout Assistant (experimental)")
        author = "Spotstone UG"
        version = "0.0.1.dev0"
        visible = True
        category = "FEATURE"
        description = _("Experimental customer checkout integration; not production-ready.")

    def ready(self):
        from . import signals  # noqa: F401

