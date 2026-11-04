"""Run against the local DEMO database only; real file-backed SQLite locking."""

import os, sys, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django

django.setup()
from concurrent.futures import ThreadPoolExecutor
from django.db import close_old_connections
from core.models import Shop, Branch
from core.tenancy import shop_context
from catalog.models import Service
from events.models import Event
from jobs.models import Job
from jobs.services import create_job

shop = Shop.objects.get(code="DEV-ONLY")
with shop_context(shop):
    branch = Branch.objects.get(code="DEMO")
    service = Service.objects.filter(mode="kg").first()
    before = set(Job.objects.values_list("id", flat=True))
    seq = branch.job_seq


def create(_):
    close_old_connections()
    try:
        with shop_context(shop):
            return create_job(
                {
                    "kg": "1.0",
                    "service": str(service.id),
                    "notes": "DEMO concurrency probe",
                },
                Branch.objects.get(pk=branch.id),
            )[0].number
    finally:
        close_old_connections()


with ThreadPoolExecutor(max_workers=4) as pool:
    numbers = list(pool.map(create, range(12)))
with shop_context(shop):
    jobs = Job.objects.exclude(id__in=before)
    events = Event.objects.filter(
        payload__job_id__in=[str(j) for j in jobs.values_list("id", flat=True)]
    )
    assert sorted(numbers) == list(range(seq + 1, seq + 13))
    assert jobs.count() == events.count() == 12
print(
    json.dumps(
        {
            "database": "file-backed SQLite",
            "workers": 4,
            "jobs": 12,
            "unique_numbers": sorted(numbers),
            "events": 12,
            "status": "PASS",
        }
    )
)
