from datetime import timedelta
from unittest.mock import patch
import pytest
from django.utils import timezone
from django.core.exceptions import ValidationError
from core.models import JobStage, Shop
from core.tenancy import shop_context
from jobs.models import Job
from jobs.services import create_job
from jobs.transitions import advance, override, claim, StaleAction
from events.models import Event


def new(s, **extra):
    return create_job(
        {"kg": "2.0", "service": str(s["service"].id), **extra}, s["branch"], s["staff"]
    )[0]


def stage(name):
    return JobStage.objects.get(name=name)


def ready(s, job):
    return advance(s["branch"], job.number, job.status_id, s["staff"])


def test_independent_cards_simple_and_full(setup_shop):
    s = setup_shop
    a = new(s)
    b = new(s)
    a = ready(s, a)
    assert a.status.is_last
    b.refresh_from_db()
    assert b.status.is_first
    s["branch"].simple_mode = False
    s["branch"].save()
    with pytest.raises(ValidationError):
        advance(s["branch"], b.number, b.status_id)
    b = advance(s["branch"], b.number, b.status_id, skip_reason="Machine not used")
    assert b.status.name == "Washing"
    e = Event.objects.filter(type="stage_changed", payload__number=b.number).get()
    assert e.payload["no_machine"] and e.payload["reason"] == "Machine not used"


def test_hidden_stage_mapping_and_preservation(setup_shop, scoped_client):
    s = setup_shop
    job = new(s)
    s["branch"].simple_mode = False
    s["branch"].save()
    job = override(
        s["branch"],
        job.number,
        job.status_id,
        stage("Drying").id,
        "Correction",
        s["staff"],
    )
    s["branch"].simple_mode = True
    s["branch"].save()
    response = scoped_client.get("/jobs/")
    assert b"in Drying" in response.content
    assert (
        b">Washing</option>"
        not in scoped_client.get(f"/jobs/{job.number}/stage/").content
    )
    job.refresh_from_db()
    assert job.status.name == "Drying"
    job = advance(s["branch"], job.number, job.status_id)
    assert job.status.name == "Ready"
    s["branch"].simple_mode = False
    s["branch"].save()
    job.refresh_from_db()
    assert job.status.name == "Ready"


def test_manual_reason_event_and_first_ready_preserved(setup_shop):
    s = setup_shop
    job = new(s)
    first = job.status_id
    job = override(
        s["branch"], job.number, first, stage("Ready").id, "Set aside", s["staff"]
    )
    initial = job.first_ready_at
    job = override(s["branch"], job.number, job.status_id, first, "Back", s["staff"])
    assert job.ready_at is None and job.first_ready_at == initial
    job = advance(s["branch"], job.number, job.status_id)
    assert job.first_ready_at == initial and job.ready_at >= initial
    e = Event.objects.filter(type="stage_overridden").order_by("seq").first()
    assert (
        e.payload["description"]
        == "Stage changed to Ready, manual override from Received"
        and e.payload["reason"] == "Set aside"
    )


@pytest.mark.parametrize("action", ["advance", "override", "claim"])
def test_stale_action_no_side_effects(setup_shop, action):
    s = setup_shop
    job = new(s)
    expected = job.status_id
    job = ready(s, job)
    before = Event.objects.count()
    with pytest.raises(StaleAction, match="already in Ready"):
        if action == "advance":
            advance(s["branch"], job.number, expected)
        elif action == "override":
            override(s["branch"], job.number, expected, stage("Received").id)
        else:
            claim(s["branch"], job.number, expected, {"pay_method": "cash"})
    job.refresh_from_db()
    assert (
        job.claimed_at is None
        and job.paid_at is None
        and Event.objects.count() == before
    )


@pytest.mark.parametrize("method", ["cash", "gcash"])
def test_claim_once_payment_recorded(setup_shop, method):
    s = setup_shop
    job = ready(s, new(s))
    expected = job.status_id
    job = claim(
        s["branch"],
        job.number,
        expected,
        {"pay_method": method, "pay_ref": "CLAIM-REF"},
        s["staff"],
    )
    assert job.claimed_at and job.paid_at
    assert (
        Event.objects.filter(type="payment_recorded").count() == 1
        and Event.objects.filter(type="job_claimed").count() == 1
    )
    with pytest.raises(StaleAction):
        claim(s["branch"], job.number, expected, {"pay_method": method})
    assert Event.objects.filter(type="payment_recorded").count() == 1


def test_prepaid_retains_original_and_claim_rollback(setup_shop):
    s = setup_shop
    job = ready(s, new(s, pay_method="gcash", pay_ref="ORIGINAL"))
    paid = job.paid_at
    with patch("jobs.transitions.append_event", side_effect=RuntimeError("injected")):
        with pytest.raises(RuntimeError):
            claim(s["branch"], job.number, job.status_id, {})
    job.refresh_from_db()
    assert job.claimed_at is None
    job = claim(s["branch"], job.number, job.status_id, {"pay_method": "cash"})
    assert (
        job.paid_at == paid and job.pay_method == "gcash" and job.pay_ref == "ORIGINAL"
    )
    assert Event.objects.filter(type="payment_recorded").count() == 1


def test_paper_ready_and_release_sheet_times(setup_shop):
    s = setup_shop
    date = (timezone.localdate() - timedelta(days=2)).isoformat()
    job = create_job(
        {
            "kg": "1",
            "service": str(s["service"].id),
            "paper": "1",
            "paper_ref": "P-9",
            "paper_date": date,
            "received_time": "08:00",
            "written_total": "90",
        },
        s["branch"],
    )[0]
    s["branch"].simple_mode = False
    s["branch"].save()
    job = advance(s["branch"], job.number, job.status_id, paper_ready=True)
    assert job.status.is_last
    d = {
        "paper_release": "1",
        "release_date": date,
        "release_time": "17:00",
        "paid_time": "16:55",
        "pay_method": "cash",
    }
    job = claim(s["branch"], job.number, job.status_id, d, s["staff"])
    assert (
        timezone.localdate(job.claimed_at).isoformat() == date
        and timezone.localtime(job.claimed_at).hour == 17
    )
    assert timezone.localtime(job.paid_at).minute == 55
    assert Event.objects.get(type="job_claimed").occurred_at == job.claimed_at


def test_claim_refuses_nonready_invalid_or_future_times(setup_shop):
    s = setup_shop
    job = new(s)
    with pytest.raises(ValidationError):
        claim(s["branch"], job.number, job.status_id, {"pay_method": "cash"})
    job = ready(s, job)
    with pytest.raises(ValidationError):
        claim(s["branch"], job.number, job.status_id, {})
    for days in [-1, 8]:
        with pytest.raises(ValidationError):
            claim(
                s["branch"],
                job.number,
                job.status_id,
                {
                    "pay_method": "cash",
                    "paper_release": "1",
                    "release_date": (
                        timezone.localdate() - timedelta(days=days)
                    ).isoformat(),
                    "release_time": "17:00",
                    "paid_time": "17:00",
                },
            )
    assert Event.objects.filter(type="payment_recorded").count() == 0


def test_ready_age_uses_arrival_and_claimed_day(setup_shop, scoped_client):
    s = setup_shop
    job = new(s)
    Job.objects.filter(pk=job.pk).update(received_at=timezone.now() - timedelta(days=5))
    job = ready(s, job)
    assert b"Ready for over 2 days" not in scoped_client.get("/jobs/").content
    Job.objects.filter(pk=job.pk).update(ready_at=timezone.now() - timedelta(days=3))
    assert b"Ready for over 2 days" in scoped_client.get("/jobs/").content
    scoped_client.post(
        f"/jobs/{job.number}/claim/",
        {"expected": str(job.status_id), "pay_method": "cash"},
    )
    assert b"1 claimed today" in scoped_client.get("/jobs/").content
    assert (
        f'data-job="{job.number}"'.encode() not in scoped_client.get("/jobs/").content
    )


def test_board_http_stale_feedback_and_scoping(setup_shop, scoped_client):
    s = setup_shop
    job = new(s)
    expected = str(job.status_id)
    assert (
        scoped_client.post(
            f"/jobs/{job.number}/advance/", {"expected": expected}
        ).status_code
        == 302
    )
    r = scoped_client.post(
        f"/jobs/{job.number}/advance/", {"expected": expected}, follow=True
    )
    assert b"already in Ready" in r.content
    assert (
        scoped_client.post("/jobs/999999/advance/", {"expected": expected}).status_code
        == 404
    )
    other = Shop.objects.create(code="FOREIGN", name="FOREIGN")
    with shop_context(other):
        foreign = JobStage.objects.create(shop=other, name="FOREIGN", sort_order=1)
    assert (
        scoped_client.post(
            f"/jobs/{job.number}/stage/",
            {"expected": str(stage("Ready").id), "target": str(foreign.id)},
        ).status_code
        == 404
    )


def test_manual_override_leaves_actual_load_running(setup_shop):
    from core.models import Machine, MachineCategory
    from machines.models import Load

    s = setup_shop
    job = new(s)
    category = MachineCategory.objects.create(
        shop=s["shop"], name="Washer", label_prefix="W"
    )
    machine = Machine.objects.create(
        shop=s["shop"], branch=s["branch"], category=category, label="W1"
    )
    load = Load.objects.create(
        shop=s["shop"],
        branch=s["branch"],
        machine=machine,
        job=job,
        started_at=timezone.now(),
    )
    override(
        s["branch"],
        job.number,
        job.status_id,
        stage("Ready").id,
        "Correction",
        s["staff"],
    )
    load.refresh_from_db()
    assert load.ended_at is None
