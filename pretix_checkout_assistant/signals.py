import logging

from django.dispatch import receiver
from django.templatetags.static import static
from django.utils.html import format_html
from pretix.presale.signals import html_head

from .automatic import should_attempt

logger = logging.getLogger(__name__)


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
    except Exception:
        logger.exception("Checkout assistant eligibility check failed")
        return ""
    if not eligible:
        return ""
    try:
        script_url = static("pretix_checkout_assistant/automatic.js")
    except (ValueError, OSError):
        logger.exception("Checkout assistant static file unavailable")
        return ""
    return format_html('<script defer src="{}"></script>', script_url)
