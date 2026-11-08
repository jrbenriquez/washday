from datetime import datetime, time
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError
from django.test import Client
from django.utils import timezone

from core.models import JobStage, Machine, MachineCategory
from core.operating_hours import require_job_operating_hours
from customers.models import Customer
from events.models import Action, Event, Outbox, Replica
from events.undo import compensate
from jobs.models import Job, JobLine
from jobs.services import create_job
from jobs.transitions import advance, claim, override
from machines.models import Load
from machines.services import start_for_job, unload
from people.context import device_context
from people.models import Device
from people.services import begin_shift, enroll, issue_code, save_staff
from supplies.models import StockEntry


def at(value):
    return datetime.fromisoformat(f"2026-11-09T{value}+08:00")


@pytest.mark.parametrize("opening,closing,clock,allowed", [
    (time(8), time(20), "07:59:59", False),
    (time(8), time(20), "08:00:00", True),
    (time(8), time(20), "19:59:59", True),
    (time(8), time(20), "20:00:00", False),
    (time(8), time(20), "00:00:00", False),
    (time(20), time(6), "20:00:00", True),
    (time(20), time(6), "00:00:00", True),
    (time(20), time(6), "05:59:59", True),
    (time(20), time(6), "06:00:00", False),
    (time(20), time(6), "19:59:59", False),
    (time(0), time(0), "12:00:00", True),
    (time(8), time(8), "07:00:00", True),
    (None, time(20), "10:00:00", False),
    (time(8), None, "10:00:00", False),
    (None, None, "10:00:00", False),
])
def test_hours_boundaries(opening, closing, clock, allowed):
    branch = SimpleNamespace(opening_time=opening, closing_time=closing)
    with timezone.override("Asia/Manila"), patch("django.utils.timezone.now", return_value=at(clock)):
        if allowed:
            require_job_operating_hours(branch)
        else:
            with pytest.raises(ValidationError):
                require_job_operating_hours(branch)


@pytest.fixture
def operating_shop(setup_shop):
    s = setup_shop
    b = s["branch"]
    b.opening_time, b.closing_time = time(8), time(20)
    b.simple_mode = False
    b.save()
    with patch("django.utils.timezone.now", return_value=at("10:00:00")):
        yield s


@pytest.mark.parametrize("role", ["cloud", "hub"])
@pytest.mark.parametrize("operation", ["unpaid", "paid", "paper", "advance", "override", "claim", "start", "unload", "undo"])
def test_closed_job_services_are_atomic(operating_shop, settings, role, operation):
    s, b = operating_shop, operating_shop["branch"]
    if role == "hub":
        settings.APP_ROLE, settings.HUB_BRANCH_ID = "hub", str(b.pk)
        b.mode = "hub"
        b.save()
        Replica.objects.create(shop=s["shop"], branch=b, writer_active=True)
    device = Device.objects.create(shop=s["shop"], branch=b, kind="shared", name="Counter")
    data = {"service": str(s["service"].pk), "kg": "3"}
    with device_context(device):
        job, _ = create_job(data, b, s["staff"])
        ready = JobStage.objects.get(is_last=True)
        washing = JobStage.objects.get(name="Washing")
        category = MachineCategory.objects.create(shop=s["shop"], name="Washer", label_prefix="W")
        machine = Machine.objects.create(shop=s["shop"], branch=b, category=category, label="W1")
        load = None
        if operation == "unload":
            load = start_for_job(b, job.number, job.status_id, washing.pk, machine.pk, s["staff"])
            job.refresh_from_db()
        if operation in ("claim", "undo"):
            override(b, job.number, job.status_id, ready.pk, staff=s["staff"])
            job.refresh_from_db()
        action = Action.objects.order_by("-event__seq").first()

        def snapshot():
            b.refresh_from_db()
            return (
                b.job_seq, b.event_seq,
                *[list(model.objects.order_by("pk").values()) for model in
                  (Job, JobLine, Customer, Event, StockEntry, Load, Action, Outbox)],
            )

        before = snapshot()
        calls = {
            "unpaid": lambda: create_job({**data, "customer_name": "Fake customer"}, b),
            "paid": lambda: create_job({**data, "pay_method": "cash"}, b),
            "paper": lambda: create_job({**data, "paper": "1", "paper_ref": "P-1", "paper_date": "2026-11-09", "received_time": "10:00", "written_total": "100"}, b),
            "advance": lambda: advance(b, job.number, job.status_id, skip_reason="No machine"),
            "override": lambda: override(b, job.number, job.status_id, ready.pk),
            "claim": lambda: claim(b, job.number, job.status_id, {"pay_method": "cash"}),
            "start": lambda: start_for_job(b, job.number, job.status_id, washing.pk, machine.pk),
            "unload": lambda: unload(b, machine.pk, load.pk),
            "undo": lambda: compensate(b, action.event_id, device),
        }
        # Keep Undo within its six-second window while crossing branch closing.
        with patch("django.utils.timezone.now", return_value=at("10:00:01")):
            b.closing_time = time(10, 0, 1)
            b.save(update_fields=["closing_time"])
            with pytest.raises(ValidationError, match="operating hours"):
                calls[operation]()
        assert snapshot() == before


@pytest.mark.parametrize("kind", ["shared", "personal"])
@pytest.mark.parametrize("clock", ["07:59:59", "20:00:00"])
def test_enrolled_devices_cannot_post_closed_jobs(operating_shop, settings, kind, clock):
    s, b = operating_shop, operating_shop["branch"]
    settings.ENABLE_DEV_BRANCH_SCOPE = False
    staff, _ = save_staff(b, "Staff", "1234")
    device = Device.objects.create(
        shop=s["shop"], branch=b, kind=kind, name="Device",
        assigned_staff=staff if kind == "personal" else None,
    )
    code, _ = issue_code(device)
    _, key, error = enroll(device, code)
    assert not error
    if kind == "personal":
        begin_shift(device, staff)
    client = Client()
    client.cookies[settings.DEVICE_COOKIE_NAME] = key
    data = {"service": str(s["service"].pk), "kg": "3"}
    assert client.post("/jobs/new/", data).status_code == 302
    job = Job.objects.get()
    target = JobStage.objects.get(is_last=True)
    # A previously opened form, or a new sign-in after closing, cannot bypass hours.
    with patch("django.utils.timezone.now", return_value=at(clock)):
        if kind == "personal" and clock == "20:00:00":
            assert client.post("/shift/", {"staff": str(staff.pk), "pin": "1234"}).status_code == 302
        response = client.post("/jobs/new/", data)
        assert response.status_code == 422
        assert b"operating hours" in response.content
        response = client.post(f"/jobs/{job.number}/stage/", {
            "expected": str(job.status_id), "target": str(target.pk), "pin": "1234",
        })
        assert response.status_code == 422
        assert b"operating hours" in response.content
        assert client.get("/jobs/").status_code == 200
    assert Job.objects.count() == 1
    job.refresh_from_db()
    assert job.status.is_first
