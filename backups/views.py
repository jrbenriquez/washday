import base64
import hashlib
import secrets
import time
from urllib.parse import urlencode
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_variables
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from owner.views import owner
from .drive import (
    DriveClient,
    DriveError,
    SCOPE,
    configured,
    cipher,
    encrypt,
    http,
    tokens,
)
from .forms import FolderForm, ScheduleForm
from .models import DriveBackup, ExportRun
from .scheduling import first_run


def config_for(request, lock=False):
    own = owner(request)
    config, _ = DriveBackup.objects.get_or_create(
        shop_id=own.shop_id, defaults={"timezone": own.shop.timezone}
    )
    if lock:
        config = DriveBackup.objects.select_for_update().get(pk=config.pk)
        if config.locked_until and config.locked_until > timezone.now():
            raise DriveError(
                "An export is running. Wait for it to finish before changing the Drive setup."
            )
    return config


def page(request, config, form=None, error=None, status=200):
    return render(
        request,
        "backups/settings.html",
        {
            "backup": config,
            "schedule_form": form or ScheduleForm(instance=config),
            "runs": ExportRun.objects.filter(backup=config).order_by("-scheduled_for")[
                :20
            ],
            "configured": configured(),
            "picker_api_key": settings.GOOGLE_DRIVE_PICKER_API_KEY,
            "picker_app_id": settings.GOOGLE_DRIVE_APP_ID,
            "error": error,
        },
        status=status,
    )


@require_http_methods(["GET", "POST"])
@never_cache
@transaction.atomic
def settings_page(request):
    config = config_for(request)
    if request.method == "POST":
        try:
            config = config_for(request, lock=True)
            form = ScheduleForm(request.POST, instance=config)
            if form.is_valid():
                config = form.save(commit=False)
                config.next_run_at = (
                    first_run(timezone.now(), config.local_time, config.timezone)
                    if config.enabled
                    else None
                )
                # Retire pending work from the replaced schedule, keeping it visible in history.
                ExportRun.objects.filter(backup=config, manual=False).exclude(
                    status="success"
                ).update(status="cancelled")
                config.save()
                messages.success(request, "Export schedule saved.")
                return redirect("drive_exports")
            return page(request, config, form, status=422)
        except DriveError as exc:
            return page(request, config, error=str(exc), status=409)
    return page(request, config)


@require_POST
@never_cache
@sensitive_variables()
def connect(request):
    owner(request)
    if not configured():
        messages.error(
            request, "Configure Google Drive OAuth and the token encryption key first."
        )
        return redirect("drive_exports")
    try:
        cipher()
    except DriveError as exc:
        messages.error(request, str(exc))
        return redirect("drive_exports")
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    request.session["drive_oauth"] = {
        "state": state,
        "verifier": verifier,
        "at": time.time(),
        "owner": str(request.owner.pk),
    }
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    return redirect(
        "https://accounts.google.com/o/oauth2/v2/auth?"
        + urlencode(
            {
                "client_id": settings.GOOGLE_DRIVE_CLIENT_ID,
                "redirect_uri": settings.GOOGLE_DRIVE_REDIRECT_URI,
                "response_type": "code",
                "scope": SCOPE,
                "state": state,
                "access_type": "offline",
                "prompt": "consent select_account",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            }
        )
    )


@require_GET
@never_cache
@sensitive_variables()
@transaction.atomic
def callback(request):
    own = owner(request)
    pending = request.session.pop("drive_oauth", {})
    if (
        not pending
        or pending.get("owner") != str(own.pk)
        or time.time() - pending.get("at", 0) > 600
        or not secrets.compare_digest(
            pending.get("state", ""), request.GET.get("state", "")
        )
    ):
        raise PermissionDenied(
            "Drive authorization expired or state did not match. Start again."
        )
    try:
        if request.GET.get("error") or not request.GET.get("code"):
            raise DriveError(
                "Drive connection was cancelled. Existing exports have not changed."
            )
        config = config_for(request, lock=True)
        data = tokens(
            grant_type="authorization_code",
            code=request.GET["code"],
            code_verifier=pending["verifier"],
            redirect_uri=settings.GOOGLE_DRIVE_REDIRECT_URI,
        )
        if not data.get("refresh_token") or not data.get("access_token"):
            raise DriveError(
                "Google did not grant background access. Reconnect and approve Drive access."
            )
        if (
            "https://www.googleapis.com/auth/drive.file"
            not in data.get("scope", "").split()
        ):
            raise DriveError(
                "Drive permission was not granted. Reconnect and approve file access."
            )
        profile = http(
            "GET",
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": "Bearer " + data["access_token"]},
        )
        config.refresh_token_encrypted = encrypt(data["refresh_token"])
        config.account_email = profile.get("email", "")
        config.connected_by = own
        config.enabled = False
        config.next_run_at = None
        config.folder_id = config.folder_name = ""
        config.save()
        ExportRun.objects.filter(backup=config).exclude(
            status__in=["success", "cancelled"]
        ).update(status="cancelled")
        messages.success(
            request, "Google Drive connected. Select a folder and save your schedule."
        )
    except DriveError as exc:
        messages.error(request, str(exc))
    return redirect("drive_exports")


@require_POST
@never_cache
@transaction.atomic
def folder(request):
    config = config_for(request)
    try:
        config = config_for(request, lock=True)
        form = FolderForm(request.POST)
        if not form.is_valid():
            return page(
                request,
                config,
                error="Select a folder or enter a valid folder name.",
                status=422,
            )
        if not config.refresh_token_encrypted:
            raise DriveError("Connect Google Drive first.")
        drive = DriveClient(config)
        selected = (
            drive.folder(form.cleaned_data["folder_id"])
            if form.cleaned_data["folder_id"]
            else drive.create_folder(form.cleaned_data["new_name"])
        )
        config.folder_id, config.folder_name = selected["id"], selected["name"]
        config.save(update_fields=["folder_id", "folder_name"])
        messages.success(request, "Export destination saved.")
    except DriveError as exc:
        return page(request, config, error=str(exc), status=422)
    return redirect("drive_exports")


@require_POST
@never_cache
def picker_token(request):
    config = config_for(request)
    try:
        if not config.refresh_token_encrypted:
            raise DriveError("Connect Drive first.")
        return JsonResponse({"access_token": DriveClient(config).access_token})
    except DriveError as exc:
        return JsonResponse({"error": str(exc)}, status=422)


@require_POST
@never_cache
@transaction.atomic
def export_now(request):
    config = config_for(request)
    try:
        config = config_for(request, lock=True)
        if not config.refresh_token_encrypted or not config.folder_id:
            raise DriveError("Connect Drive and select a destination first.")
        if (
            ExportRun.objects.filter(backup=config, manual=True)
            .exclude(status__in=["success", "cancelled"])
            .exists()
        ):
            raise DriveError("A test export is already queued. Check its status below.")
        ExportRun.objects.create(
            shop_id=config.shop_id,
            backup=config,
            manual=True,
            scheduled_for=timezone.now(),
        )
        messages.success(
            request,
            "Test export queued. The scheduled worker will process it on its next tick.",
        )
    except DriveError as exc:
        messages.error(request, str(exc))
    return redirect("drive_exports")


@require_POST
@never_cache
@transaction.atomic
def disconnect(request):
    config = config_for(request)
    try:
        config = config_for(request, lock=True)
        config.refresh_token_encrypted = config.account_email = config.folder_id = (
            config.folder_name
        ) = ""
        config.enabled = False
        config.connected_by = None
        config.next_run_at = None
        config.save()
        ExportRun.objects.filter(backup=config).exclude(status="success").update(
            status="cancelled"
        )
        request.session.pop("drive_oauth", None)
        messages.success(
            request,
            "Drive disconnected and saved credentials removed. Existing Drive files are kept.",
        )
    except DriveError as exc:
        messages.error(request, str(exc))
    return redirect("drive_exports")
