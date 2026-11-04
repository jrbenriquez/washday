import uuid
from datetime import timedelta
from zoneinfo import ZoneInfo
from django.db import transaction
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone
from core.tenancy import shop_context
from .drive import DriveClient, DriveError
from .models import DriveBackup, ExportRun
from .reports import build_reports
from .scheduling import following_run


def process_backup(backup_id):
    now = timezone.now()
    lease = uuid.uuid4()
    # Compare-and-set works on SQLite and PostgreSQL, including overlapping cron ticks.
    claimed = (
        DriveBackup.unscoped.filter(pk=backup_id)
        .filter(Q(locked_until=None) | Q(locked_until__lte=now))
        .update(lease_id=lease, locked_until=now + timedelta(hours=1))
    )
    if not claimed:
        return False
    config = DriveBackup.unscoped.select_related("shop", "connected_by").get(
        pk=backup_id
    )
    with shop_context(config.shop):
        run = None
        try:
            if (
                config.shop.archived_at
                or not config.connected_by
                or not config.connected_by.active
                or not config.refresh_token_encrypted
                or not config.folder_id
            ):
                return False
            run = (
                ExportRun.objects.filter(backup=config, manual=True)
                .exclude(status__in=["success", "cancelled"])
                .filter(Q(retry_at=None) | Q(retry_at__lte=now))
                .order_by("scheduled_for")
                .first()
            )
            if (
                not run
                and config.enabled
                and config.next_run_at
                and config.next_run_at <= now
            ):
                run, _ = ExportRun.objects.get_or_create(
                    backup=config,
                    scheduled_for=config.next_run_at,
                    manual=False,
                    defaults={"shop_id": config.shop_id},
                )
            if not run or (run.retry_at and run.retry_at > now):
                return False
            run.status = "running"
            run.attempts += 1
            run.error = ""
            run.save(update_fields=["status", "attempts", "error"])
            drive = DriveClient(config)
            files = build_reports(config.shop, run.scheduled_for, config.timezone)
            day = run.scheduled_for.astimezone(ZoneInfo(config.timezone)).date()
            # Shop/run suffix avoids collisions when several shops share a parent folder.
            run.folder_name = (
                f"{day.isoformat()} - {config.shop.code} - {str(run.pk)[:8]}"
            )
            folder = drive.run_folder(config.folder_id, run.folder_name, str(run.pk))
            run.folder_id = folder["id"]
            run.save(update_fields=["folder_id", "folder_name"])
            for filename, content, mime in files:
                drive.upload(run.folder_id, filename, content, mime)
            with transaction.atomic():
                # A replaced connection or expired lease must not advance another worker's schedule.
                current = DriveBackup.objects.select_for_update().get(pk=config.pk)
                if current.lease_id != lease:
                    return False
                run.status = "success"
                run.completed_at = timezone.now()
                run.retry_at = None
                run.save(update_fields=["status", "completed_at", "retry_at"])
                if not run.manual:
                    current.next_run_at = following_run(run.scheduled_for, config)
                    current.save(update_fields=["next_run_at"])
            return True
        except Exception as exc:
            # Do not persist raw API exceptions: they may contain credentials or customer data.
            if run:
                run.status = "failed"
                run.error = (
                    str(exc)
                    if isinstance(exc, DriveError)
                    else "Export failed. Check server configuration and worker health, then retry."
                )
                run.retry_at = timezone.now() + timedelta(minutes=5)
                run.save(update_fields=["status", "error", "retry_at"])
            return False
        finally:
            DriveBackup.unscoped.filter(pk=config.pk, lease_id=lease).update(
                lease_id=None, locked_until=None
            )


def run_due(limit=20):
    now = timezone.now()
    manual_ready = (
        ExportRun.unscoped.filter(backup_id=OuterRef("pk"), manual=True)
        .exclude(status__in=["success", "cancelled"])
        .filter(Q(retry_at=None) | Q(retry_at__lte=now))
    )
    scheduled_waiting = ExportRun.unscoped.filter(
        backup_id=OuterRef("pk"),
        manual=False,
        scheduled_for=OuterRef("next_run_at"),
        retry_at__gt=now,
    )
    ids = (
        DriveBackup.unscoped.filter(
            shop__archived_at=None,
            connected_by__active=True,
        )
        .exclude(refresh_token_encrypted="")
        .exclude(folder_id="")
        .filter(Q(locked_until=None) | Q(locked_until__lte=now))
        .alias(
            manual_ready=Exists(manual_ready),
            scheduled_waiting=Exists(scheduled_waiting),
        )
        .filter(
            Q(enabled=True, next_run_at__lte=now, scheduled_waiting=False)
            | Q(manual_ready=True)
        )
        .order_by("next_run_at")
        .values_list("pk", flat=True)
    )
    completed = 0
    # Bound work per tick. A failed shop never stops the remaining shops.
    for backup_id in list(ids[:limit]):
        completed += process_backup(backup_id)
    return completed
