from django.shortcuts import render
from core.models import Settings
from .services import verify_pin


def pin_guard(request, *actions):
    device = getattr(request, "device", None)
    if not device or device.kind != "shared":
        return None
    policy = Settings.objects.get(shop_id=device.shop_id)
    if not policy.pin_enabled or not set(actions).intersection(policy.pin_actions):
        return None
    error = ""
    if request.POST.get("pin"):
        staff, error = verify_pin(device, request.POST["pin"])
        if staff:
            request.staff = staff
            return None
    fields = [
        (k, v)
        for k, values in request.POST.lists()
        if k not in ("pin", "csrfmiddlewaretoken")
        for v in values
    ]
    return render(
        request,
        "people/pin.html",
        {
            "fields": fields,
            "action_url": request.path,
            "error": error,
            "action_label": ", ".join(actions),
        },
        status=422 if error else 200,
    )
