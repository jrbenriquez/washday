"""Run the same staff services/auth/payment/Undo flow in both serving roles."""

from datetime import time

import pytest
from django.test import Client
from django.utils import timezone

from core.models import JobStage, Machine, MachineCategory
from events.models import Action, Outbox, Replica
from jobs.models import Job
from jobs.transitions import advance
from machines.services import start_for_job, unload
from owner.workspace import collections
from people.context import device_context
from people.models import Device
from people.services import begin_shift, enroll, issue_code, save_staff


@pytest.mark.parametrize("role", ["cloud", "hub"])
def test_staff_lifecycle_pin_and_undo_in_each_role(setup_shop, settings, role):
    s = setup_shop
    b = s["branch"]
    b.simple_mode = False
    b.closing_time = time(23, 59)
    b.opening_time = b.closing_time
    b.save(update_fields=["simple_mode", "opening_time", "closing_time"])
    staff, _ = save_staff(b, "Role staff", "1234")
    personal = Device.objects.create(
        shop=s["shop"], branch=b, kind="personal", name="Role phone", assigned_staff=staff
    )
    shared = Device.objects.create(
        shop=s["shop"], branch=b, kind="shared", name="Role tablet"
    )
    personal_code, _ = issue_code(personal)
    shared_code, _ = issue_code(shared)
    washer = MachineCategory.objects.create(
        shop=s["shop"], name="Role washer", label_prefix="W"
    )
    dryer = MachineCategory.objects.create(
        shop=s["shop"], name="Role dryer", label_prefix="D"
    )
    w = Machine.objects.create(shop=s["shop"], branch=b, category=washer, label="W1")
    d = Machine.objects.create(shop=s["shop"], branch=b, category=dryer, label="D1")
    for name, category in [("Washing", washer), ("Drying", dryer)]:
        stage = JobStage.objects.get(name=name)
        stage.machine_category = category
        stage.move_on_when_unloaded = name == "Drying"
        stage.save()
    settings.APP_ROLE = role
    settings.HUB_BRANCH_ID = str(b.pk)
    settings.ENABLE_DEV_BRANCH_SCOPE = False
    if role == "hub":
        b.mode = "hub"
        b.writer_epoch = 1
        b.save(update_fields=["mode", "writer_epoch"])
        b.refresh_from_db()
        Replica.objects.create(
            shop=s["shop"], branch=b, writer_active=True, acknowledged_seq=b.event_seq
        )
    with device_context(personal):
        _, personal_key, error = enroll(personal, personal_code)
        assert not error
        begin_shift(personal, staff)
    phone = Client()
    phone.cookies["washday_device"] = personal_key
    data = {"service": str(s["service"].pk), "kg": "3", "pay_method": "cash"}
    assert phone.post("/jobs/new/", data).status_code == 302
    job = Job.objects.get()
    with device_context(personal):
        washing = JobStage.objects.get(name="Washing")
        drying = JobStage.objects.get(name="Drying")
        load = start_for_job(b, job.number, job.status_id, washing.pk, w.pk, staff)
        unload(b, w.pk, load.pk, staff)
        job.refresh_from_db()
        load = start_for_job(b, job.number, job.status_id, drying.pk, d.pk, staff)
        unload(b, d.pk, load.pk, staff)
        job.refresh_from_db()
        advance(b, job.number, job.status_id, staff)
        job.refresh_from_db()
    assert (
        phone.post(
            f"/jobs/{job.number}/claim/", {"expected": str(job.status_id)}
        ).status_code
        == 302
    )
    action = Action.objects.filter(device=personal).order_by("-event__seq").first()
    assert phone.post(f"/undo/{action.event_id}/").status_code == 302
    job.refresh_from_db()
    assert job.claimed_at is None and job.paid_at
    with device_context(shared):
        _, shared_key, error = enroll(shared, shared_code)
        assert not error
    tablet = Client()
    tablet.cookies["washday_device"] = shared_key
    assert tablet.post("/jobs/new/", {**data, "pay_method": ""}).status_code == 302
    unpaid = Job.objects.exclude(pk=job.pk).get()
    ready = JobStage.objects.get(is_last=True)
    stage_url = f"/jobs/{unpaid.number}/stage/"
    correction = {"expected": str(unpaid.status_id), "target": str(ready.pk)}
    assert tablet.post(stage_url, correction).status_code == 200
    unpaid.refresh_from_db()
    assert unpaid.status.is_first
    assert tablet.post(stage_url, {**correction, "pin": "1234"}).status_code == 302
    unpaid.refresh_from_db()
    claim_url = f"/jobs/{unpaid.number}/claim/"
    payment = {"expected": str(unpaid.status_id), "pay_method": "gcash"}
    assert tablet.post(claim_url, payment).status_code == 200
    assert tablet.post(claim_url, {**payment, "pin": "1234"}).status_code == 302
    action = Action.objects.filter(device=shared).order_by("-event__seq").first()
    assert tablet.post(f"/undo/{action.event_id}/").status_code == 302
    unpaid.refresh_from_db()
    assert not unpaid.paid_at and not unpaid.claimed_at
    assert collections([b], timezone.localdate())["total"] == job.total
    assert Outbox.objects.exists() == (role == "hub")
