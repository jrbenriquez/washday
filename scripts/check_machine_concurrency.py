import os, sys, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django

django.setup()
from concurrent.futures import ThreadPoolExecutor
from django.db import close_old_connections
from django.core.exceptions import ValidationError
from core.models import Shop, Branch, Machine, JobStage
from core.tenancy import shop_context
from catalog.models import Service
from jobs.services import create_job
from machines.models import Load
from machines.services import start_for_job, unload

shop = Shop.objects.get(code="DEV-ONLY")
with shop_context(shop):
    branch = Branch.objects.get(code="DEMO")
    was_simple = branch.simple_mode
    branch.simple_mode = False
    branch.save(update_fields=["simple_mode"])
    stage = JobStage.objects.get(name="Washing")
    machine = Machine.objects.get(label="W1")
    service = Service.objects.filter(mode="kg").first()
    assert not Load.objects.filter(machine=machine, ended_at=None).exists()
    jobs = [
        create_job(
            {
                "kg": "1",
                "service": str(service.id),
                "notes": "DEMO machine concurrency probe",
            },
            branch,
        )[0]
        for _ in range(4)
    ]


def worker(job):
    close_old_connections()
    try:
        with shop_context(shop):
            try:
                return {
                    "status": "STARTED",
                    "load": str(
                        start_for_job(
                            Branch.objects.get(pk=branch.pk),
                            job.number,
                            job.status_id,
                            stage.id,
                            machine.id,
                        ).id
                    ),
                }
            except ValidationError as e:
                return {"status": "REFUSED", "reason": " ".join(e.messages)}
    finally:
        close_old_connections()


with ThreadPoolExecutor(max_workers=4) as pool:
    result = list(pool.map(worker, jobs))
with shop_context(shop):
    assert (
        sum(r["status"] == "STARTED" for r in result) == 1
        and Load.objects.filter(machine=machine, ended_at=None).count() == 1
    )
    winner = Load.objects.get(machine=machine, ended_at=None)
    unload(branch, machine.id, winner.id)
    branch.simple_mode = was_simple
    branch.save(update_fields=["simple_mode"])
print(
    json.dumps(
        {
            "status": "PASS",
            "database": "file-backed SQLite",
            "workers": 4,
            "started": 1,
            "refused": 3,
            "one_open_load": True,
            "results": result,
        }
    )
)
