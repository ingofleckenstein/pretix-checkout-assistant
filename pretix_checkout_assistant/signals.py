from django.dispatch import receiver
from django.templatetags.static import static
from django.utils.html import format_html
from pretix.presale.signals import html_head

from .automatic import should_attempt


@receiver(html_head, dispatch_uid="checkout_assistant_experimental_head")
def checkout_head(sender, request, **kwargs):
    match = getattr(request, "resolver_match", None)
    if not match or match.kwargs.get("step") != "questions":
        return ""
    step = next((s for s in getattr(request, "_checkout_flow", ()) if s.identifier == "questions"), None)
    if not step or not should_attempt(request, step):
        return ""
    return format_html('<script defer src="{}"></script>', static("pretix_checkout_assistant/automatic.js"))

