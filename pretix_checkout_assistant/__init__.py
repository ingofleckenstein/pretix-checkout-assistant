"""Experimental checkout assistant; not production-ready."""

from .apps import CheckoutAssistantApp

default_app_config = "pretix_checkout_assistant.apps.CheckoutAssistantApp"
PretixPluginMeta = CheckoutAssistantApp.PretixPluginMeta
