from datetime import timedelta
from unittest.mock import patch
from decimal import Decimal
import pytest
from django.core.exceptions import ValidationError
from django.http import Http404
from django.utils import timezone
from django.db import transaction, IntegrityError
from core.models import MachineCategory, Machine, JobStage, Branch
from jobs.services import create_job
from jobs.transitions import override, StaleAction
from machines.models import Load
from machines.services import start_for_job, self_service, unload
from events.models import Event


@pytest.fixture
def machine_setup(setup_shop):
    s = setup_shop
    b = s["branch"]
    b.simple_mode = False
    b.save(update_fields=["simple_mode"])
    w = MachineCategory.objects.create(
        shop=s["shop"], name="Washer", label_prefix="W", uses_wash_supplies=True
    )
    d = MachineCategory.objects.create(
        shop=s["shop"], name="Dryer", label_prefix="D", sort_order=1
    )
    wash = JobStage.objects.get(name="Washing")
    wash.machine_category = w
    wash.save()
    dry = JobStage.objects.get(name="Drying")
    dry.machine_category = d
    dry.move_on_when_unloaded = True
    dry.save()
    w1 = Machine.objects.create(shop=s["shop"], branch=b, category=w, label="W1")
    w2 = Machine.objects.create(shop=s["shop"], branch=b, category=w, label="W2")
    d1 = Machine.objects.create(shop=s["shop"], branch=b, category=d, label="D1")
    return {**s, "w1": w1, "w2": w2, "d1": d1, "wash": wash, "dry": dry}


def job(s, **extra):
    return create_job(
        {"kg": "1", "service": str(s["service"].id), **extra}, s["branch"], s["staff"]
    )[0]


def start(s, j, m="w1", target="wash"):
    return start_for_job(
        s["branch"], j.number, j.status_id, s[target].id, s[m].id, s["staff"]
    )


def test_board_start_and_monitoring_only_grid(machine_setup, scoped_client):
    s = machine_setup
    j = job(s)
    r = scoped_client.post(f"/jobs/{j.number}/advance/", {"expected": str(j.status_id)})
    assert "/machine/?target=" in r.url
    start(s, j)
    j.refresh_from_db()
    assert j.status.name == "Washing"
    r = scoped_client.get("/machines/")
    assert b"Monitor loads here" in r.content and b"Open Jobs board" in r.content
    assert b"Unloading" not in r.content and b"Unload W1" in r.content
    assert b'name="job"' not in r.content and b">Start job<" not in r.content
    assert (
        scoped_client.post(
            f"/machines/{s['w2'].id}/start/",
            {"job": str(j.id), "service": str(s["load"].id), "pay_method": "cash"},
        ).status_code
        == 404
    )
    assert Load.objects.count() == 1


def test_busy_oos_category_foreign_and_stale_refused(machine_setup):
    s = machine_setup
    a = job(s)
    b = job(s)
    start(s, a)
    with pytest.raises(ValidationError):
        start(s, b)
    assert Load.objects.count() == 1
    s["w2"].out_of_service = True
    s["w2"].save(update_fields=["out_of_service"])
    with pytest.raises(ValidationError):
        start(s, b, "w2")
    with pytest.raises(ValidationError):
        start(s, b, "d1")
    with pytest.raises(StaleAction):
        start(s, a, "w2")
    other = Branch.objects.create(shop=s["shop"], name="OTHER", number=2, code="OTHER")
    m = Machine.objects.create(
        shop=s["shop"], branch=other, category=s["w1"].category, label="FOREIGN"
    )
    with pytest.raises(Http404):
        start_for_job(s["branch"], b.number, b.status_id, s["wash"].id, m.id)
    assert Event.objects.filter(type="load_started").count() == 1


def test_normal_departure_ends_previous_and_manual_override_does_not(machine_setup):
    s = machine_setup
    j = job(s)
    w = start(s, j)
    j.refresh_from_db()
    d = start(s, j, "d1", "dry")
    w.refresh_from_db()
    j.refresh_from_db()
    assert w.ended_at and j.status.name == "Drying" and d.ended_at is None
    override(
        s["branch"],
        j.number,
        j.status_id,
        JobStage.objects.get(is_last=True).id,
        "Correction",
    )
    d.refresh_from_db()
    assert d.ended_at is None
    unload(s["branch"], s["d1"].id, d.id)
    j.refresh_from_db()
    assert j.status.name == "Ready"
    assert Event.objects.filter(type="load_ended").count() == 2


def test_last_unload_moves_only_once_and_next_machine_stage_waits(machine_setup):
    s = machine_setup
    j = job(s)
    load = start(s, j)
    j.refresh_from_db()
    # Washing is not auto-next. Drying asks a machine, even if move_on is set.
    s["wash"].move_on_when_unloaded = True
    s["wash"].save(update_fields=["move_on_when_unloaded"])
    unload(s["branch"], s["w1"].id, load.id)
    j.refresh_from_db()
    assert j.status.name == "Washing"
    d = start(s, j, "d1", "dry")
    j.refresh_from_db()
    unload(s["branch"], s["d1"].id, d.id)
    j.refresh_from_db()
    assert j.status.name == "Folding"
    before = Event.objects.count()
    with pytest.raises(ValidationError):
        unload(s["branch"], s["d1"].id, d.id)
    assert Event.objects.count() == before


def test_multiload_last_and_current_board_stage_start(machine_setup):
    s = machine_setup
    j = job(s)
    w = start(s, j)
    j.refresh_from_db()
    w2 = start(s, j, "w2")
    assert Load.objects.filter(job=j, ended_at=None).count() == 2
    unload(s["branch"], s["w1"].id, w.id)
    j.refresh_from_db()
    assert j.status.name == "Washing"
    start(s, j, "d1", "dry")
    w2.refresh_from_db()
    assert w2.ended_at


def test_custom_immediate_predecessor_and_any_category_explicit_target(machine_setup):
    s = machine_setup
    j = job(s)
    custom = MachineCategory.objects.create(
        shop=s["shop"], name="Steam press", label_prefix="P"
    )
    m = Machine.objects.create(
        shop=s["shop"], branch=s["branch"], category=custom, label="P1"
    )
    press = JobStage.objects.create(
        shop=s["shop"],
        name="Pressing",
        sort_order=3,
        ask_for_machine=True,
        machine_category=custom,
    )
    # Move Folding out of the way, preserving the intended active stage order.
    folding = JobStage.objects.get(name="Folding")
    folding.sort_order = 4
    folding.save()
    ready = JobStage.objects.get(is_last=True)
    ready.sort_order = 5
    ready.save()
    with pytest.raises(ValidationError):
        start_for_job(s["branch"], j.number, j.status_id, press.id, m.id)
    j = override(s["branch"], j.number, j.status_id, s["dry"].id)
    load = start_for_job(s["branch"], j.number, j.status_id, press.id, m.id)
    j.refresh_from_db()
    assert j.status.name == "Pressing"
    unload(s["branch"], m.id, load.id)
    # Any-category target is selected explicitly on board; no grid fallback is invented.
    press.machine_category = None
    press.save(update_fields=["machine_category"])
    load = start_for_job(s["branch"], j.number, j.status_id, press.id, s["w1"].id)
    assert load.machine_id == s["w1"].id


def test_self_service_requires_active_load_service_and_snapshots(
    machine_setup, scoped_client
):
    s = machine_setup
    assert b"Paid self-service" in scoped_client.get("/machines/").content
    l = self_service(s["branch"], s["w1"].id, s["load"].id, "gcash", s["staff"])
    assert l.self_service and l.job_id is None and l.amount == Decimal("150.00")
    s["load"].price = 999
    s["load"].save(update_fields=["price"])
    l.refresh_from_db()
    assert l.amount == Decimal("150.00")
    assert Event.objects.get(type="self_service_started").payload["method"] == "gcash"
    assert b"150.00" in scoped_client.get("/jobs/?view=history").content
    with pytest.raises(Http404):
        self_service(s["branch"], s["w2"].id, s["service"].id, "cash")
    s["load"].archived_at = timezone.now()
    s["load"].save(update_fields=["archived_at"])
    assert b"Paid self-service" not in scoped_client.get("/machines/").content


def test_check_threshold_elapsed_today_and_no_countdown(machine_setup, scoped_client, monkeypatch):
    noon = timezone.localtime().replace(hour=12, minute=0, second=0, microsecond=0)
    monkeypatch.setattr(timezone, "now", lambda: noon)
    s = machine_setup
    j = job(s)
    l = start(s, j)
    Load.objects.filter(pk=l.pk).update(
        started_at=timezone.now() - timedelta(minutes=90)
    )
    r = scoped_client.get("/machines/")
    assert (
        b"Check it" in r.content
        and b"In use" in r.content
        and b"1 loads today" in r.content
    )
    assert b"countdown" not in r.content
    unload(s["branch"], s["w1"].id, l.id)
    assert b"Unloaded after 90 min" in scoped_client.get("/machines/").content


def test_simple_paper_and_transactional_start_failure(machine_setup, scoped_client):
    s = machine_setup
    j = job(s)
    with patch("machines.services.append_event", side_effect=RuntimeError("injected")):
        with pytest.raises(RuntimeError):
            start(s, j)
    assert not Load.objects.exists()
    j.refresh_from_db()
    assert j.status.is_first
    s["branch"].simple_mode = True
    s["branch"].save(update_fields=["simple_mode"])
    with pytest.raises(ValidationError):
        start(s, j)
    assert scoped_client.get("/machines/").status_code == 404
    assert "◉ Machines".encode() not in scoped_client.get("/jobs/").content
    s["branch"].simple_mode = False
    s["branch"].save(update_fields=["simple_mode"])
    day = (timezone.localdate() - timedelta(days=1)).isoformat()
    paper = job(
        s,
        paper="1",
        paper_ref="P-2",
        paper_date=day,
        received_time="08:00",
        written_total="99",
    )
    with pytest.raises(ValidationError):
        start(s, paper)
    assert (
        scoped_client.get(
            f"/jobs/{paper.number}/machine/?target={s['wash'].id}"
        ).status_code
        == 404
    )


def test_db_constraint_and_unload_expected_guard(machine_setup):
    s = machine_setup
    j = job(s)
    l = start(s, j)
    with transaction.atomic():
        with pytest.raises(IntegrityError), transaction.atomic():
            Load.objects.create(
                shop=s["shop"],
                branch=s["branch"],
                machine=s["w1"],
                job=j,
                started_at=timezone.now(),
            )
    with pytest.raises(ValidationError):
        unload(s["branch"], s["w1"].id, "wrong expected id")
    assert Load.objects.get(pk=l.pk).ended_at is None
