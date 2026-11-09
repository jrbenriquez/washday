from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST
from core.models import Branch, Settings
from people.models import Device, DeviceSetupCode, Staff
from people.services import save_staff, issue_code, revoke_device, assign_device_staff, audit
from .forms import StaffForm, DeviceForm, DeviceAssignmentForm, HoursForm, PolicyForm


def owner(request):
    if not request.owner:
        raise PermissionDenied()
    return request.owner


def scoped_branch(value):
    try:
        return get_object_or_404(Branch, pk=value)
    except (ValidationError, ValueError):
        from django.http import Http404

        raise Http404()


def dashboard_context(request, **extra):
    owner(request)
    devices = list(
        Device.objects.select_related("branch", "assigned_staff").order_by("branch__name", "name")
    )
    now = timezone.now()
    for device in devices:
        device.assignment_form = DeviceAssignmentForm(
            branch=device.branch, prefix=str(device.pk),
            initial={"assigned_staff": device.assigned_staff_id},
        )
        challenge = DeviceSetupCode.objects.filter(
            device=device, used_at=None, expires_at__gt=now
        ).first()
        device.code_seconds = (
            max(0, int((challenge.expires_at - now).total_seconds()))
            if challenge
            else None
        )
    return {
        "branches": Branch.objects.order_by("number"),
        "devices": devices,
        "device_form": DeviceForm(),
        "hours_form": HoursForm(),
        **extra,
    }


@require_GET
@never_cache
def login(request):
    if request.owner:
        return redirect("owner_dashboard")
    return render(
        request,
        "owner/login.html",
        {"google_configured": settings.GOOGLE_OAUTH_CONFIGURED},
    )


@require_GET
@never_cache
def home(request):
    extra = {}
    if request.GET.get("setup") == "shared":
        branch = scoped_branch(request.GET.get("branch"))
        extra = {
            "selected_branch": branch,
            "device_form": DeviceForm(initial={"name": f"{branch.name} counter", "kind": "shared"}),
        }
    return render(request, "owner/home.html", dashboard_context(request, **extra))


@require_POST
@never_cache
def staff_new(request):
    from .workspace import staff_context

    own = owner(request)
    branch = scoped_branch(request.POST.get("branch"))
    form = StaffForm(request.POST)
    if form.is_valid():
        try:
            staff, pin = save_staff(
                branch,
                form.cleaned_data["name"],
                form.cleaned_data["pin"],
                owner_email=own.email,
            )
            return render(
                request,
                "owner/staff_saved.html",
                {"saved_staff": staff, "shown_pin": pin},
            )
        except ValidationError as e:
            form.add_error(None, e)
    return render(
        request,
        "owner/staff.html",
        staff_context(
            request, staff_form=form, selected_branch=branch, chosen=[branch]
        ),
        status=422,
    )


@require_POST
@never_cache
def staff_update(request, staff_id):
    from .workspace import staff_context

    own = owner(request)
    staff = get_object_or_404(Staff, pk=staff_id)
    target_branch = (
        scoped_branch(request.POST.get("branch"))
        if request.POST.get("branch")
        else staff.branch
    )
    active = request.POST.get("active") == "1"
    pin = request.POST.get("pin", "").strip()
    try:
        if request.POST.get("generate") == "1":
            import secrets
            from django.contrib.auth.hashers import check_password

            for _ in range(100):
                pin = f"{secrets.randbelow(10000):04d}"
                if not any(
                    check_password(pin, s.pin_hash)
                    for s in Staff.objects.filter(branch=target_branch, active=True)
                ):
                    break
            else:
                raise ValidationError("Could not generate a fresh PIN. Try again.")
        staff, pin = save_staff(
            target_branch,
            request.POST.get("name", staff.name),
            pin,
            staff=staff,
            active=active,
            owner_email=own.email,
        )
        if pin:
            return render(
                request,
                "owner/staff_saved.html",
                {"saved_staff": staff, "shown_pin": pin},
            )
        messages.success(request, "Staff access updated.")
        return redirect("owner_staff")
    except ValidationError as e:
        return render(
            request,
            "owner/staff.html",
            staff_context(request, error=" ".join(e.messages)),
            status=422,
        )


def code_page(request, device, code, challenge):
    url = request.build_absolute_uri(
        reverse("device_start") + "?invite=" + str(device.id)
    )
    if device.branch.mode == "hub" and device.branch.hub_url:
        url = device.branch.hub_url.rstrip("/") + reverse("device_start") + "?invite=" + str(device.id)
    return render(
        request,
        "owner/code.html",
        {
            "enrolling_device": device,
            "setup_code": code,
            "expires_at": challenge.expires_at,
            "install_url": url,
            "browser_setup": settings.DEVICE_SETUP_ALLOW_BROWSER,
        },
    )


@require_POST
@never_cache
@transaction.atomic
def device_new(request):
    own = owner(request)
    branch = scoped_branch(request.POST.get("branch"))
    Branch.objects.select_for_update().get(pk=branch.pk)
    form = DeviceForm(request.POST, branch=branch)
    if form.is_valid():
        device = Device.objects.create(
            shop_id=own.shop_id, branch=branch, **form.cleaned_data
        )
        code, challenge = issue_code(device, own.email)
        return code_page(request, device, code, challenge)
    return render(
        request,
        "owner/home.html",
        dashboard_context(request, device_form=form, selected_branch=branch),
        status=422,
    )


@require_POST
@never_cache
def device_code(request, device_id):
    own = owner(request)
    device = get_object_or_404(Device, pk=device_id)
    code, challenge = issue_code(device, own.email)
    return code_page(request, device, code, challenge)


@require_POST
@never_cache
@transaction.atomic
def device_assign(request, device_id):
    own = owner(request)
    device = get_object_or_404(Device, pk=device_id, kind="personal")
    Branch.objects.select_for_update().get(pk=device.branch_id)
    form = DeviceAssignmentForm(request.POST, branch=device.branch, prefix=str(device.pk))
    if form.is_valid():
        device = assign_device_staff(device, form.cleaned_data["assigned_staff"], own.email)
        code, challenge = issue_code(device, own.email)
        return code_page(request, device, code, challenge)
    return render(
        request, "owner/home.html",
        dashboard_context(request, error="Choose an active staff member at this phone’s branch."),
        status=422,
    )


@require_POST
def device_revoke(request, device_id):
    own = owner(request)
    device = get_object_or_404(Device, pk=device_id)
    revoke_device(device, own.email)
    messages.success(
        request, "Device revoked. Its current key no longer grants access."
    )
    return redirect("owner_home")


@require_POST
@transaction.atomic
def hours(request, branch_id):
    own = owner(request)
    branch = scoped_branch(branch_id)
    form = HoursForm(request.POST)
    if form.is_valid():
        branch = Branch.objects.select_for_update().get(pk=branch.pk)
        config = Settings.objects.select_for_update().get(shop_id=own.shop_id)
        branch.opening_time = form.cleaned_data["opening_time"]
        branch.closing_time = form.cleaned_data["closing_time"]
        branch.save(update_fields=["opening_time", "closing_time"])
        config.version += 1
        config.save(update_fields=["version"])
        audit(
            branch,
            "branch_hours_updated",
            "Branch opening/closing hours updated",
            owner=own.email,
        )
        messages.success(
            request, "Branch hours saved. Staff sessions expire 24 hours after sign-in."
        )
        return redirect("owner_branch_manage")
    return render(
        request,
        "owner/home.html",
        dashboard_context(request, error="Enter valid opening and closing times."),
        status=422,
    )


@require_POST
@transaction.atomic
def policy(request):
    from .workspace import settings_context

    own = owner(request)
    form = PolicyForm(request.POST)
    if form.is_valid():
        branches = list(Branch.objects.select_for_update().order_by("pk"))
        config = Settings.objects.select_for_update().get(shop_id=own.shop_id)
        config.pin_enabled = form.cleaned_data["pin_enabled"]
        config.pin_actions = form.cleaned_data["pin_actions"]
        config.version += 1
        config.save(update_fields=["pin_enabled", "pin_actions", "version"])
        for branch in branches:
            audit(
                branch,
                "pin_policy_updated",
                "Shared-device PIN policy updated",
                owner=own.email,
            )
        messages.success(request, "Shared-device PIN rules saved.")
        return redirect("owner_shop_settings")
    return render(
        request,
        "owner/settings.html",
        settings_context(request, policy_form=form),
        status=422,
    )


def unavailable(request):
    return HttpResponseForbidden(
        "Washday uses allow-listed Google sign-in. Password login and public signup are disabled."
    )


def account_login(request):
    return redirect("owner_login")
