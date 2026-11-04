from django.db import models
from core.models import TenantModel


class Staff(TenantModel):
    branch = models.ForeignKey("core.Branch", on_delete=models.PROTECT)
    name = models.CharField(max_length=120)
    pin_hash = models.CharField(max_length=256)
    active = models.BooleanField(default=True)


class Device(TenantModel):
    branch = models.ForeignKey("core.Branch", on_delete=models.PROTECT)
    kind = models.CharField(
        max_length=10,
        choices=[("shared", "Shared counter"), ("personal", "Personal phone")],
    )
    name = models.CharField(max_length=120)
    key_hash = models.CharField(max_length=64, unique=True, null=True, blank=True)
    enrol_epoch = models.PositiveIntegerField(default=0)
    config_revision = models.PositiveIntegerField(default=0)
    key_revision = models.PositiveIntegerField(default=0)
    last_seen_at = models.DateTimeField(null=True)
    revoked_at = models.DateTimeField(null=True)
    pin_failures = models.PositiveSmallIntegerField(default=0)
    pin_locked_until = models.DateTimeField(null=True)
    setup_failures = models.PositiveSmallIntegerField(default=0)
    setup_locked_until = models.DateTimeField(null=True)


class DeviceSetupCode(TenantModel):
    device = models.ForeignKey(
        Device, on_delete=models.PROTECT, related_name="setup_codes"
    )
    code_hash = models.CharField(max_length=256)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True)

    class Meta(TenantModel.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["device"],
                condition=models.Q(used_at=None),
                name="one_unused_device_code",
            )
        ]


class Shift(TenantModel):
    staff = models.ForeignKey(Staff, on_delete=models.PROTECT)
    device = models.ForeignKey(Device, on_delete=models.PROTECT)
    started_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True)
    ended_by = models.CharField(max_length=20, blank=True)

    class Meta(TenantModel.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["device"],
                condition=models.Q(ended_at=None),
                name="one_open_device_shift",
            )
        ]
