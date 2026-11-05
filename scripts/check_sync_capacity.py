"""File-backed retention fixture: 30 days at 600 event envelopes/day."""

import io
import json
import os
import sys
import tempfile
import uuid
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / ".agents/work/undo-offline/evidence"
OUT.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="washday-capacity-") as temp:
    branch_id = uuid.uuid4()
    os.environ.update(
        DJANGO_SETTINGS_MODULE="config.settings",
        APP_ROLE="hub",
        HUB_BRANCH_ID=str(branch_id),
        SQLITE_PATH=str(Path(temp) / "hub.sqlite3"),
        DJANGO_DEBUG="1",
    )
    os.environ.pop("PGDATABASE", None)
    import django

    django.setup()
    from django.core.management import call_command
    from django.db import connection
    from django.utils import timezone

    from core.models import Branch, Shop
    from core.tenancy import shop_context
    from events.models import Event, Outbox
    from events.records import fields

    call_command("migrate", stdout=io.StringIO(), verbosity=0)
    shop = Shop.objects.create(name="TEST retention shop", code="TEST-RETENTION")
    with shop_context(shop):
        branch = Branch.objects.create(
            id=branch_id,
            shop=shop,
            name="TEST hub",
            number=1,
            code="TEST",
            mode="hub",
            writer_epoch=1,
        )
        count = 30 * 600
        oldest = timezone.now() - timedelta(days=30)
        for offset in range(0, count, 500):
            events = [
                Event(
                    shop=shop,
                    branch=branch,
                    seq=n + 1,
                    type="capacity_probe",
                    payload={"fixture": "x" * 1024},
                    occurred_at=oldest + timedelta(seconds=n * 144),
                )
                for n in range(offset, min(offset + 500, count))
            ]
            Event.objects.bulk_create(events)
            Outbox.objects.bulk_create(
                [
                    Outbox(
                        shop=shop,
                        event=e,
                        frame={
                            "protocol": 1,
                            "epoch": 1,
                            "event": fields(e),
                            "records": [],
                            "job_seq": 1000,
                        },
                    )
                    for e in events
                ]
            )
        assert (
            Event.objects.count() == count
            and Outbox.objects.filter(sent_at=None).count() == count
        )
        with connection.cursor() as cursor:
            cursor.execute("PRAGMA journal_mode")
            mode = cursor.fetchone()[0]
            cursor.execute("PRAGMA page_count")
            pages = cursor.fetchone()[0]
            cursor.execute("PRAGMA page_size")
            size = cursor.fetchone()[0]
        assert mode == "wal"
        first = list(
            Outbox.objects.order_by("event__seq").values_list("event__seq", flat=True)[
                :500
            ]
        )
        assert first == list(range(1, 501))
        result = {
            "status": "PASS",
            "fixture": "30 days × 600 envelopes/day; 1 KiB event payload plus full envelope metadata",
            "unsent_events": count,
            "journal_mode": mode,
            "database_bytes": pages * size,
            "retention_evictions": 0,
            "batch_limit": 500,
            "physical_time_elapsed": "not a 30-day soak; deterministic capacity/retention fixture",
        }
        (OUT / "capacity.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result))
