from events.journal import recorded_action
from django.conf import settings
from django.db.models import F
import hashlib
import re
import secrets
from datetime import datetime, timedelta
from django.contrib.auth.hashers import (
    make_password,
    check_password,
    is_password_usable,
)
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from core.models import Branch
from core.tenancy import shop_context
from jobs.services import append_event
from .models import Device, DeviceSetupCode, Staff, Shift
from .context import device_context


def token_digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def authenticate_device(token):
    """Resolve a high-entropy bearer credential before entering tenant scope."""
    if not token:
        return None
    return (
        Device.unscoped.select_related("branch__shop")
        .filter(
            key_hash=token_digest(token),
            kind__in=["shared", "personal"],
            revoked_at=None,
            branch__mode="hub" if settings.APP_ROLE == "hub" else "direct",
            enrol_epoch=F("branch__writer_epoch"),
            shop__archived_at=None,
        )
        .filter(**({"branch_id": settings.HUB_BRANCH_ID} if settings.APP_ROLE == "hub" else {})).first()
    )


def lock_branch(device):
    return Branch.objects.select_for_update().get(pk=device.branch_id)


def audit(branch, kind, description, staff=None, **payload):
    if settings.APP_ROLE == "cloud" and branch.mode == "hub":
        from events.models import ConfigurationAudit
        return ConfigurationAudit.objects.create(shop_id=branch.shop_id,branch=branch,kind=kind,
            payload={"description":description,**payload},at=timezone.now())
    return append_event(
        branch, kind, {"description": description, **payload}, timezone.now(), staff
    )


def _close_shift(shift, at, reason):
    if settings.APP_ROLE == "cloud" and shift.device.branch.mode == "hub":
        # The hub observes the access change on pull and closes its own shift.
        return
    shift.ended_at = at
    shift.ended_by = reason
    shift.save(update_fields=["ended_at", "ended_by"])
    append_event(
        shift.device.branch,
        "shift_ended",
        {
            "description": f"Shift ended · {shift.staff.name} · {reason}",
            "shift_id": str(shift.id),
            "device_id": str(shift.device_id),
        },
        at,
        shift.staff,
    )


def close_device_shifts(device, at, reason):
    for shift in (
        Shift.objects.select_for_update()
        .filter(device=device, ended_at=None)
        .select_related("staff", "device__branch")
    ):
        _close_shift(shift, at, reason)


def _locked(device, prefix, now):
    until = getattr(device, prefix + "_locked_until")
    if until and until > now:
        return True
    if until:
        setattr(device, prefix + "_failures", 0)
        setattr(device, prefix + "_locked_until", None)
    return False


def _failure(device, prefix, now):
    field = prefix + "_failures"
    until = prefix + "_locked_until"
    setattr(device, field, getattr(device, field) + 1)
    if getattr(device, field) >= 5:
        setattr(device, field, 0)
        setattr(device, until, now + timedelta(minutes=1))
    device.save(update_fields=[field, until])
    return (
        "Too many attempts. Try again in one minute."
        if getattr(device, until)
        else (
            "The setup code is not valid. Try again."
            if prefix == "setup"
            else "The PIN is not valid. Try again."
        )
    )


@transaction.atomic
def issue_code(device, owner_email=""):
    branch = lock_branch(device)
    device = Device.objects.select_for_update().get(pk=device.pk)
    now = timezone.now()
    previous = DeviceSetupCode.objects.filter(device=device, used_at=None).first()
    code = f"{secrets.randbelow(1000000):06d}"
    while previous and check_password(code, previous.code_hash):
        code = f"{secrets.randbelow(1000000):06d}"
    DeviceSetupCode.objects.filter(device=device, used_at=None).update(used_at=now)
    result = DeviceSetupCode.objects.create(
        shop_id=device.shop_id,
        device=device,
        code_hash=make_password(code),
        expires_at=now + timedelta(minutes=15),
    )
    device.setup_failures = 0
    device.setup_locked_until = None
    device.config_revision += 1
    device.save(update_fields=["setup_failures", "setup_locked_until", "config_revision"])
    audit(
        branch,
        "device_code_issued",
        f"Device setup code issued · {device.name}",
        device_id=str(device.id),
        owner=owner_email,
    )
    return code, result


@recorded_action
def enroll(public_device, code):
    with shop_context(public_device.shop_id), transaction.atomic():
        branch = lock_branch(public_device)
        device = Device.objects.select_for_update().get(pk=public_device.pk)
        now = timezone.now()
        from events.sync.authority import assert_writer
        try:
            assert_writer(branch)
        except ValidationError:
            return (
                None,
                None,
                "This branch requires its hub address. Ask the owner for the correct setup link.",
            )
        if _locked(device, "setup", now):
            return None, None, "Too many attempts. Try again in one minute."
        challenge = (
            DeviceSetupCode.objects.select_for_update()
            .filter(device=device, used_at=None)
            .first()
        )
        valid = bool(
            challenge
            and challenge.expires_at > now
            and re.fullmatch(r"[0-9]{6}", code)
            and check_password(code, challenge.code_hash)
        )
        if not valid:
            return None, None, _failure(device, "setup", now)
        challenge.used_at = now
        challenge.save(update_fields=["used_at"])
        close_device_shifts(device, now, "reenrolled")
        token = secrets.token_urlsafe(32)
        device.key_hash = token_digest(token)
        device.enrol_epoch = branch.writer_epoch
        device.key_revision = device.config_revision
        device.revoked_at = None
        device.last_seen_at = now
        device.setup_failures = 0
        device.setup_locked_until = None
        device.save(
            update_fields=[
                "key_hash",
                "enrol_epoch",
                "key_revision",
                "revoked_at",
                "last_seen_at",
                "setup_failures",
                "setup_locked_until",
            ]
        )
        with device_context(device):
            audit(
                branch,
                "device_enrolled",
                f"Device enrolled · {device.name}",
                device_id=str(device.id),
            )
        return device, token, ""


@transaction.atomic
def verify_pin(device, pin, staff_id=None):
    lock_branch(device)
    device = Device.objects.select_for_update().get(pk=device.pk)
    now = timezone.now()
    if device.revoked_at:
        return (
            None,
            "This device is no longer enrolled. Ask the owner for a new setup code.",
        )
    if _locked(device, "pin", now):
        return None, "Too many attempts. Try again in one minute."
    people = Staff.objects.filter(branch_id=device.branch_id, active=True)
    if staff_id:
        people = people.filter(pk=staff_id)
    staff = next(
        (
            s
            for s in people
            if is_password_usable(s.pin_hash)
            and re.fullmatch(r"[0-9]{4}", pin)
            and check_password(pin, s.pin_hash)
        ),
        None,
    )
    if not staff:
        return None, _failure(device, "pin", now)
    device.pin_failures = 0
    device.pin_locked_until = None
    device.save(update_fields=["pin_failures", "pin_locked_until"])
    return staff, ""


@recorded_action
def current_shift(device):
    shift = (
        Shift.objects.filter(device=device, ended_at=None)
        .select_related("staff", "device__branch")
        .first()
    )
    if not shift:
        return None
    if (
        shift.ends_at > timezone.now()
        and shift.staff.active
        and shift.staff.branch_id == device.branch_id
    ):
        return shift
    with transaction.atomic():
        lock_branch(device)
        shift = (
            Shift.objects.select_for_update()
            .filter(pk=shift.pk, ended_at=None)
            .select_related("staff", "device__branch")
            .first()
        )
        if shift:
            closing = shift.ends_at <= timezone.now()
            _close_shift(
                shift,
                shift.ends_at if closing else timezone.now(),
                "closing" if closing else "staff_changed",
            )
    return None


@transaction.atomic
@recorded_action
def begin_shift(device, staff):
    branch = lock_branch(device)
    device = Device.objects.select_for_update().get(pk=device.pk)
    if device.kind != "personal" or device.revoked_at:
        raise ValidationError("A personal enrolled device is required.")
    if not staff.active or staff.branch_id != branch.id:
        raise ValidationError("Choose an active staff member at this branch.")
    if Shift.objects.filter(device=device, ended_at=None).exists():
        raise ValidationError("End the current shift before starting another.")
    if branch.closing_time is None:
        raise ValidationError(
            "Ask the owner to set this branch’s closing time before starting a shift."
        )
    now = timezone.now()
    local = timezone.localtime(now)
    ends = timezone.make_aware(datetime.combine(local.date(), branch.closing_time))
    if ends <= now:
        ends += timedelta(days=1)
    shift = Shift.objects.create(
        shop_id=device.shop_id, device=device, staff=staff, started_at=now, ends_at=ends
    )
    audit(
        branch,
        "shift_started",
        f"Shift started · {staff.name}",
        staff,
        shift_id=str(shift.id),
        device_id=str(device.id),
    )
    return shift


@transaction.atomic
@recorded_action
def end_shift(device):
    lock_branch(device)
    close_device_shifts(device, timezone.now(), "staff")


@transaction.atomic
def revoke_device(device, owner_email=""):
    branch = lock_branch(device)
    device = Device.objects.select_for_update().get(pk=device.pk)
    now = timezone.now()
    device.revoked_at = now
    device.key_hash = None
    device.config_revision += 1
    device.save(update_fields=["revoked_at", "key_hash", "config_revision"])
    DeviceSetupCode.objects.filter(device=device, used_at=None).update(used_at=now)
    close_device_shifts(device, now, "revoked")
    audit(
        branch,
        "device_revoked",
        f"Device revoked · {device.name}",
        device_id=str(device.id),
        owner=owner_email,
    )


@transaction.atomic
def save_staff(branch, name, pin="", staff=None, active=True, owner_email=""):
    moving = staff is not None and staff.branch_id != branch.pk
    if moving:
        list(Branch.objects.select_for_update().order_by("pk"))
        if not pin:
            raise ValidationError(
                "Set or generate a fresh PIN when moving staff to another branch."
            )
    branch = Branch.objects.select_for_update().get(pk=branch.pk)
    name = name.strip()
    if not name or len(name) > 120:
        raise ValidationError("Enter a staff name up to 120 characters.")
    if not pin and not staff:
        for _ in range(100):
            candidate = f"{secrets.randbelow(10000):04d}"
            if not any(
                check_password(candidate, s.pin_hash)
                for s in Staff.objects.filter(branch=branch, active=True)
            ):
                pin = candidate
                break
        else:
            raise ValidationError("Could not generate an unused PIN. Try again.")
    if pin and not re.fullmatch(r"[0-9]{4}", pin):
        raise ValidationError("A PIN must be exactly four digits.")
    others = Staff.objects.filter(branch=branch, active=True)
    if staff:
        others = others.exclude(pk=staff.pk)
    if pin and any(check_password(pin, s.pin_hash) for s in others):
        raise ValidationError(
            "That PIN is already used by active staff at this branch."
        )
    if staff and active and not staff.active and not pin:
        raise ValidationError("Set a fresh PIN when reactivating staff.")
    if staff is None:
        staff = Staff(shop_id=branch.shop_id, branch=branch)
    elif moving:
        previous_branch = staff.branch
        staff.branch = branch
        audit(
            previous_branch,
            "staff_transferred",
            f"Staff moved to {branch.name} · {staff.name}",
            staff_id=str(staff.id),
            owner=owner_email,
        )
    staff.name = name
    staff.active = active
    if pin:
        staff.pin_hash = make_password(pin)
    staff.save()
    if pin or not active:
        for shift in (
            Shift.objects.select_for_update()
            .filter(staff=staff, ended_at=None)
            .select_related("staff", "device__branch")
        ):
            _close_shift(
                shift, timezone.now(), "pin_reset" if active else "deactivated"
            )
    audit(
        branch,
        "staff_updated",
        f"Staff {'updated' if staff.pk else 'created'} · {staff.name}",
        staff_id=str(staff.id),
        owner=owner_email,
    )
    return staff, pin
