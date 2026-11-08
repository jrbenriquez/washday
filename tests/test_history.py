from datetime import timedelta, datetime
from zoneinfo import ZoneInfo
from django.utils import timezone
from core.models import Branch, JobStage
from jobs.services import create_job, append_event
from jobs.transitions import advance, claim, override
from jobs.history import project, day_of


def create(s, **extra):
    return create_job(
        {"kg": "2", "service": str(s["service"].id), **extra}, s["branch"], s["staff"]
    )[0]


def ready(s, j):
    return advance(s["branch"], j.number, j.status_id, s["staff"])


def test_event_projection_does_not_depend_on_job_active_state(
    setup_shop, scoped_client
):
    s = setup_shop
    j = ready(
        s,
        create(
            s, customer_name="TEST Ada", customer_phone="0999-123", notes="Blue bag"
        ),
    )
    j = claim(
        s["branch"],
        j.number,
        j.status_id,
        {"pay_method": "gcash", "pay_ref": "GC-1"},
        s["staff"],
    )
    rows, events = project(s["branch"])
    assert len(rows) == 1
    r = rows[0]
    assert (
        r["status"] == "Claimed"
        and r["customer"] == "TEST Ada"
        and r["paid_amount"] == j.total
        and r["reference"] == "GC-1"
    )
    for term in [str(j.number), "Ada", "0999-123", "Blue bag", "Claimed", "gcash"]:
        response = scoped_client.get(
            "/jobs/", {"view": "list", "date": "2000-01-01", "q": term}
        )
        assert (
            str(j.number).encode() in response.content
            and b"all dates" in response.content
        )
    response = scoped_client.get("/jobs/?view=history")
    assert (
        b"Released <b>1" in response.content
        and b"GCash" in response.content
        and b"GC-1" in response.content
    )
    response = scoped_client.get(f"/jobs/{j.number}/history/")
    for text in [
        "Received",
        "Stage changed to Ready",
        "Paid",
        "Released",
        "TEST staff",
        "Claim stub",
    ]:
        assert text.encode() in response.content


def test_paper_dates_summary_and_provenance(setup_shop, scoped_client):
    s = setup_shop
    day = timezone.localdate() - timedelta(days=2)
    j = create(
        s,
        paper="1",
        paper_ref="P-7",
        paper_date=day.isoformat(),
        received_time="08:00",
        written_total="99",
        pay_method="cash",
        paid_time="08:10",
    )
    j = ready(s, j)
    j = claim(
        s["branch"],
        j.number,
        j.status_id,
        {
            "paper_release": "1",
            "release_date": (day + timedelta(days=1)).isoformat(),
            "release_time": "09:00",
        },
        s["staff"],
    )
    r = scoped_client.get("/jobs/", {"view": "list", "date": day.isoformat()})
    assert b"P-7" in r.content
    r = scoped_client.get("/jobs/", {"view": "history", "date": day.isoformat()})
    assert (
        b"Received <b>1" in r.content
        and b"Released <b>0" in r.content
        and b"105.15" in r.content
    )
    r = scoped_client.get(
        "/jobs/", {"view": "history", "date": (day + timedelta(days=1)).isoformat()}
    )
    assert b"Released <b>1" in r.content
    r = scoped_client.get(
        "/jobs/", {"view": "list", "date": timezone.localdate().isoformat()}
    )
    assert f'href="/jobs/{j.number}/history/"'.encode() not in r.content
    r = scoped_client.get("/jobs/", {"view": "list", "q": "P-7"})
    assert b"P-7" in r.content
    r = scoped_client.get(f"/jobs/{j.number}/history/")
    assert b"Received on paper as P-7, entered by TEST staff" in r.content


def test_day_boundary_manila():
    z = ZoneInfo("UTC")
    assert day_of(datetime(2026, 1, 1, 15, 59, tzinfo=z)).isoformat() == "2026-01-01"
    assert day_of(datetime(2026, 1, 1, 16, 0, tzinfo=z)).isoformat() == "2026-01-02"


def test_nonjob_events_and_selfservice_summary(setup_shop, scoped_client):
    s = setup_shop
    from django.db import transaction

    with transaction.atomic():
        append_event(
            s["branch"],
            "stock_received",
            {"description": "Received TEST stock"},
            timezone.now(),
            s["staff"],
        )
        append_event(
            s["branch"],
            "self_service_started",
            {"amount": "150.00", "method": "cash", "description": "Self-service W1"},
            timezone.now(),
            s["staff"],
        )
    r = scoped_client.get("/jobs/?view=history")
    assert (
        b"Received TEST stock" in r.content
        and b"150.00" in r.content
        and b"Self-service W1" in r.content
    )
    assert b"Received <b>0" in r.content


def test_branch_isolation_same_numbers_and_404(setup_shop, scoped_client):
    s = setup_shop
    create(s)
    b = Branch.objects.create(
        shop=s["shop"], name="SECRET BRANCH", code="B2", number=2,
        opening_time=s["branch"].opening_time, closing_time=s["branch"].closing_time,
    )
    other = create_job(
        {"kg": "1", "service": str(s["service"].id), "notes": "SECRET other branch"},
        b,
        s["staff"],
    )[0]
    assert b"SECRET" not in scoped_client.get("/jobs/?view=history").content
    assert scoped_client.get(f"/jobs/{other.number}/history/").status_code == 404
    assert scoped_client.get("/jobs/?view=list&date=invalid").status_code == 422
    assert b"No jobs match" in scoped_client.get("/jobs/?view=list&q=zzzzzz").content


def test_timeline_override_and_dropoff_context(setup_shop, scoped_client):
    s = setup_shop
    j = create(s, pay_method="gcash", pay_ref="AT-IN")
    j = override(
        s["branch"],
        j.number,
        j.status_id,
        JobStage.objects.get(is_last=True).id,
        "Correction reason",
        s["staff"],
    )
    r = scoped_client.get(f"/jobs/{j.number}/history/")
    assert (
        b"at drop-off" in r.content
        and b"Correction reason" in r.content
        and b"manual override from Received" in r.content
    )
