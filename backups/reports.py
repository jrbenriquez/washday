"""Operational exports: complete business snapshot plus local-day activity CSVs.

Authentication records, PIN/key hashes, setup codes and Drive credentials are
intentionally outside the export schema. The snapshot is data, not a DB restore.
"""

import csv
import io
import json
import uuid
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from django.apps import apps
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Q
from django.utils import timezone
from core.tenancy import shop_context

# Explicit table allowlist prevents a future credentials table being exported.
TABLES = {
    "core.Branch": (),
    "core.Settings": (),
    "core.JobStage": (),
    "core.MachineCategory": (),
    "core.Machine": (),
    "customers.Customer": (),
    "catalog.Service": (),
    "catalog.AddOn": (),
    "catalog.Fee": (),
    "catalog.PieceItem": (),
    "catalog.PieceVariant": (),
    "catalog.SupplyType": (),
    "catalog.AddOnUse": (),
    "people.Staff": (),
    "people.Device": (),
    "people.Shift": ("started_at", "ended_at"),
    "jobs.Job": ("received_at", "paid_at", "claimed_at", "ready_at", "created_at"),
    "jobs.JobLine": ("job__received_at", "job__paid_at", "job__claimed_at"),
    "machines.Load": ("started_at", "ended_at"),
    "supplies.StockEntry": ("at",),
    "supplies.StockCount": ("at",),
    "supplies.StockCountLine": ("count__at",),
    "supplies.SupplyRequest": ("created_at",),
    "events.Event": ("occurred_at",),
}
EXCLUDE = {
    "pin_hash",
    "key_hash",
    "pin_failures",
    "pin_locked_until",
    "setup_failures",
    "setup_locked_until",
}


def encode(value):
    return json.dumps(value, cls=DjangoJSONEncoder, ensure_ascii=False)


def csv_cell(value):
    if isinstance(value, (dict, list)):
        value = encode(value)
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value  # Prevent spreadsheet formula execution.
    return value


def build_reports(shop, scheduled_for, tz_name):
    zone = ZoneInfo(tz_name)
    day = scheduled_for.astimezone(zone).date()
    start = datetime.combine(day, time.min, zone)
    end = datetime.combine(day + timedelta(days=1), time.min, zone)
    snapshot = {
        "shop": {"id": str(shop.pk), "name": shop.name, "code": shop.code},
        "tables": {},
    }
    manifest = {
        "schema_version": 1,
        "shop_id": str(shop.pk),
        "report_date": day.isoformat(),
        "timezone": tz_name,
        "scheduled_for": scheduled_for.isoformat(),
        "generated_at": timezone.now().isoformat(),
        "activity_start": start.isoformat(),
        "activity_end_exclusive": end.isoformat(),
        "notes": "Activity CSVs contain available records for this local calendar day. Reference CSVs and snapshot.json contain current data at generation time, including all history. A run before midnight cannot include later activity. Missed runs are generated from current data, not historical point-in-time snapshots. Authentication secrets and logo image bytes are excluded.",
        "tables": {},
    }
    files = []
    with shop_context(shop):
        event_model = apps.get_model("events.Event")
        # Stage changes can concern jobs received on an earlier date.
        changed_jobs = []
        for payload in event_model.objects.filter(
            occurred_at__gte=start, occurred_at__lt=end
        ).values_list("payload", flat=True):
            value = payload.get("job_id") if isinstance(payload, dict) else None
            if value:
                try:
                    changed_jobs.append(uuid.UUID(str(value)))
                except ValueError:
                    pass
        for label, dates in TABLES.items():
            model = apps.get_model(label)
            fields = [
                f.attname for f in model._meta.concrete_fields if f.name not in EXCLUDE
            ]
            query = model.objects.order_by("pk")
            snapshot["tables"][label] = list(query.values(*fields))
            if dates:
                predicate = Q()
                for field in dates:
                    predicate |= Q(**{field + "__gte": start, field + "__lt": end})
                if label == "jobs.Job":
                    predicate |= Q(pk__in=changed_jobs)
                elif label == "jobs.JobLine":
                    predicate |= Q(job_id__in=changed_jobs)
                query = query.filter(predicate)
            rows = list(query.values_list(*fields))
            stream = io.StringIO(newline="")
            writer = csv.writer(stream)
            writer.writerow(fields)
            writer.writerows([csv_cell(v) for v in row] for row in rows)
            filename = label.lower().replace(".", "_") + ".csv"
            files.append((filename, stream.getvalue().encode("utf-8-sig"), "text/csv"))
            manifest["tables"][label] = {
                "rows": len(rows),
                "scope": "daily_activity" if dates else "current_reference",
            }
    files.append(("snapshot.json", encode(snapshot).encode(), "application/json"))
    files.append(("manifest.json", encode(manifest).encode(), "application/json"))
    return files
