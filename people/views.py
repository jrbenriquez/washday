from django.conf import settings
from django.db import transaction
from django.http import Http404, JsonResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from django.views.decorators.cache import never_cache
from django.core.exceptions import ValidationError
from .models import Device, Staff
from .services import enroll, verify_pin, begin_shift, end_shift, authenticate_device


def invitation(request):
    value = request.GET.get("invite") or request.POST.get("invite")
    if not value:
        return None
    try:
        device = (
            Device.unscoped.select_related("branch__shop")
            .filter(pk=value, shop__archived_at=None)
            .first()
        )
    except (ValidationError, ValueError):
        raise Http404()
    if not device:
        raise Http404()
    return device


@require_GET
def home(request):
    if request.device:
        return redirect(
            "shift"
            if request.device.kind == "personal" and not request.shift
            else "board"
            if request.device.kind == "personal"
            else "new"
        )
    if request.dev_scope:
        return redirect("new")
    if request.owner:
        return redirect("owner_home")
    return render(request, "people/welcome.html")


@require_GET
@never_cache
def start(request):
    device = invitation(request)
    return render(
        request,
        "people/install.html",
        {"invitation": device, "install_branch": device.branch if device else None},
    )


@require_http_methods(["GET", "POST"])
@never_cache
def setup(request):
    device = invitation(request)
    if request.method == "GET":
        existing = authenticate_device(
            request.COOKIES.get(settings.DEVICE_COOKIE_NAME, "")
        )
        if existing and (device is None or device.pk == existing.pk):
            return redirect("home")
    error = ""
    if request.method == "POST" and device:
        enrolled, token, error = enroll(device, request.POST.get("code", ""))
        if enrolled:
            response = redirect("shift" if enrolled.kind == "personal" else "new")
            response.set_cookie(
                settings.DEVICE_COOKIE_NAME,
                token,
                max_age=settings.DEVICE_COOKIE_MAX_AGE,
                httponly=True,
                secure=not settings.DEBUG,
                samesite="Lax",
            )
            return response
    return render(
        request,
        "people/setup.html",
        {
            "invitation": device,
            "install_branch": device.branch if device else None,
            "error": error,
            "allow_browser": settings.DEVICE_SETUP_ALLOW_BROWSER,
        },
        status=422 if error else 200,
    )


@require_GET
def manifest(request):
    device = invitation(request)
    if not device:
        raise Http404()
    return JsonResponse(
        {
            "id": f"/device/{device.id}",
            "name": device.branch.shop.name,
            "short_name": "Washday",
            "start_url": reverse("device_setup") + "?invite=" + str(device.id),
            "scope": "/",
            "display": "standalone",
            "background_color": "#E8F5F5",
            "theme_color": "#2537A0",
            "icons": [
                {
                    "src": "/static/img/app-icon.svg",
                    "sizes": "any",
                    "type": "image/svg+xml",
                }
            ],
        },
        content_type="application/manifest+json",
    )


@require_http_methods(["GET", "POST"])
@never_cache
@transaction.atomic
def shift(request):
    if not request.device:
        return redirect("device_setup")
    if request.device.kind != "personal":
        return redirect("new")
    if request.shift:
        return redirect("board")
    error = ""
    if request.method == "POST":
        value = request.POST.get("staff", "")
        try:
            staff, error = verify_pin(
                request.device,
                request.POST.get("pin", ""),
                value if value else "00000000-0000-0000-0000-000000000000",
            )
        except (ValidationError, ValueError):
            staff, error = verify_pin(
                request.device, "", "00000000-0000-0000-0000-000000000000"
            )
        if staff:
            try:
                begin_shift(request.device, staff)
                return redirect("board")
            except ValidationError as e:
                error = " ".join(e.messages)
    return render(
        request,
        "people/shift.html",
        {
            "people": Staff.objects.filter(branch=request.branch, active=True).order_by(
                "name"
            ),
            "error": error,
        },
        status=422 if error else 200,
    )


@require_POST
def end(request):
    if request.device:
        end_shift(request.device)
    return redirect(
        "shift" if request.device and request.device.kind == "personal" else "new"
    )
