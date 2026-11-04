from datetime import time
from django.db import models
from core.models import TenantModel


class DriveBackup(TenantModel):
    connected_by = models.ForeignKey(
        "core.ShopOwner", null=True, on_delete=models.PROTECT
    )
    account_email = models.EmailField(blank=True)
    refresh_token_encrypted = models.TextField(blank=True)
    folder_id = models.CharField(max_length=200, blank=True)
    folder_name = models.CharField(max_length=240, blank=True)
    enabled = models.BooleanField(default=False)
    every_days = models.PositiveSmallIntegerField(default=1)
    local_time = models.TimeField(default=time(22))
    timezone = models.CharField(max_length=64, default="Asia/Manila")
    next_run_at = models.DateTimeField(null=True)
    lease_id = models.UUIDField(null=True)
    locked_until = models.DateTimeField(null=True)

    class Meta(TenantModel.Meta):
        constraints = [
            models.UniqueConstraint(fields=["shop"], name="one_drive_backup_per_shop")
        ]


class ExportRun(TenantModel):
    backup = models.ForeignKey(DriveBackup, on_delete=models.PROTECT)
    scheduled_for = models.DateTimeField()
    manual = models.BooleanField(default=False)
    status = models.CharField(max_length=12, default="pending")
    folder_id = models.CharField(max_length=200, blank=True)
    folder_name = models.CharField(max_length=240, blank=True)
    attempts = models.PositiveIntegerField(default=0)
    retry_at = models.DateTimeField(null=True)
    completed_at = models.DateTimeField(null=True)
    error = models.CharField(max_length=300, blank=True)

    class Meta(TenantModel.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["backup", "scheduled_for", "manual"],
                name="unique_drive_export_run",
            )
        ]
