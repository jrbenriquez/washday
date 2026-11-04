from django.contrib import messages

from .journal import last_action


def success(request, text):
    """Attach Undo only to the operation that actually produced this message."""
    receipt = last_action()
    tag = "undo-" + str(receipt.event_id) if receipt else ""
    messages.success(request, text, extra_tags=tag)
