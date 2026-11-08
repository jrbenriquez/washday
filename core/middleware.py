from datetime import timedelta
from django.conf import settings
from django.shortcuts import redirect
from django.utils import timezone
from core.models import Branch, ShopOwner
from core.tenancy import shop_context
from people.models import Device, Staff
from people.context import device_context
from people.services import authenticate_device, current_shift
from django.http import HttpResponseNotFound, HttpResponse


class ShopMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.branch = None
        request.staff = None
        request.device = None
        request.shift = None
        request.owner = None
        request.dev_scope = False
        if settings.APP_ROLE == "hub" and request.path.startswith(
            ("/owner/", "/accounts/", "/admin/", "/hijack/")
        ):
            return HttpResponseNotFound()
        request.sensitive_post_parameters = ("pin", "code")
        if request.user.is_authenticated:
            request.owner = (
                ShopOwner.unscoped.filter(
                    user=request.user, active=True, shop__archived_at=None
                )
                .select_related("shop")
                .first()
            )
        # Owner and staff identities never substitute for one another.
        if request.path.startswith("/owner/"):
            if request.path != "/owner/login/" and not request.owner:
                return redirect("owner_login")
            with (
                shop_context(request.owner.shop_id if request.owner else None),
                device_context(None),
            ):
                return self.get_response(request)
        if request.path.startswith(
            (
                "/accounts/",
                "/admin/",
                "/hijack/",
                "/sync/",
                "/health/",
                "/device/start/",
                "/device/setup/",
                "/device/manifest.webmanifest",
                "/static/",
                settings.MEDIA_URL,
            )
        ):
            with shop_context(None), device_context(None):
                return self.get_response(request)
        token = request.COOKIES.get(settings.DEVICE_COOKIE_NAME, "")
        device = authenticate_device(token)
        if device:
            if settings.APP_ROLE == "hub":
                from events.models import Replica

                with shop_context(device.shop_id):
                    if not Replica.objects.filter(
                        branch=device.branch, writer_active=True, frozen=False
                    ).exists():
                        return HttpResponse(
                            "This hub is preparing or its writer has been frozen. Use the active branch address.",
                            status=503,
                        )
            request.device = device
            request.branch = device.branch
            with shop_context(device.shop_id), device_context(device):
                if (
                    request.method == "POST"
                    or not device.last_seen_at
                    or timezone.now() - device.last_seen_at > timedelta(seconds=60)
                ):
                    Device.objects.filter(pk=device.pk).update(
                        last_seen_at=timezone.now()
                    )
                if device.kind == "personal":
                    request.shift = current_shift(device)
                    request.staff = request.shift.staff if request.shift else None
                    if not request.shift and request.path not in (
                        "/",
                        "/shift/",
                        "/shift/end/",
                    ):
                        return redirect("shift")
                return self.get_response(request)
        # Fixture bypass is explicit, development-only, and never rescues an invalid credential.
        if (
            not token
            and settings.DEBUG
            and settings.ENABLE_DEV_BRANCH_SCOPE
            and settings.DEV_BRANCH_ID
        ):
            branch = (
                Branch.unscoped.select_related("shop")
                .filter(pk=settings.DEV_BRANCH_ID)
                .first()
            )
            if branch:
                request.branch = branch
                request.dev_scope = True
                with shop_context(branch.shop_id), device_context(None):
                    request.staff = (
                        Staff.objects.filter(
                            pk=settings.DEV_STAFF_ID, branch=branch, active=True
                        ).first()
                        if settings.DEV_STAFF_ID
                        else None
                    )
                    return self.get_response(request)
        if request.path == "/":
            with shop_context(None), device_context(None):
                return self.get_response(request)
        response = redirect("device_setup")
        if token:
            response.delete_cookie(settings.DEVICE_COOKIE_NAME)
        return response


def context(request):
    branch = getattr(request, "branch", None)
    owner = getattr(request, "owner", None)
    badges = {}
    if branch:
        from events.models import Action

        if getattr(request, "device", None):
            action = (
                Action.objects.filter(branch=branch, device=request.device)
                .select_related("event")
                .order_by("-event__seq")
                .first()
            )
            if (
                action
                and not action.undone_at
                and timezone.now() - action.created_at <= timedelta(seconds=6)
            ):
                badges["undo_action"] = action
                badges["undo_message_tag"] = "undo-" + str(action.event_id)
                badges["undo_expires"] = (
                    action.created_at + timedelta(seconds=6)
                ).isoformat()
        from jobs.models import Job
        from machines.models import Load
        from core.models import Settings

        badges["ready_count"] = Job.objects.filter(
            branch=branch, claimed_at=None, status__is_last=True
        ).count()
        if not branch.simple_mode:
            policy = Settings.objects.get(shop_id=branch.shop_id)
            badges["machine_check_count"] = Load.objects.filter(
                branch=branch,
                ended_at=None,
                started_at__lte=timezone.now()
                - timedelta(minutes=policy.check_after_min),
            ).count()
    return {
        **badges,
        "shop": branch.shop if branch else owner.shop if owner else None,
        "serving_hub": settings.APP_ROLE == "hub",
        "branch": getattr(request, "branch", None),
        "owner": getattr(request, "owner", None),
        "device": getattr(request, "device", None),
        "shift": getattr(request, "shift", None),
        "staff": getattr(request, "staff", None),
        "dev_scope": getattr(request, "dev_scope", False),
        "app_theme": "dark" if request.COOKIES.get("app_theme") == "dark" else "light",
    }
