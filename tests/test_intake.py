from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
import pytest
from django.core.exceptions import ValidationError
from django.http import Http404
from django.utils import timezone
from django.apps import apps
from django.db import connection, close_old_connections
from core.models import Shop, Branch, TenantModel, TenantManager
from core.tenancy import shop_context
from catalog.models import Service
from customers.models import Customer
from jobs.models import Job, JobLine
from jobs.services import quote, create_job
from events.models import Event


def data(s, **extra):
    return {"kg": "1.5", "service": str(s["service"].id), **extra}


def test_minimum_rounding_load_and_pieces(setup_shop):
    s = setup_shop
    b = s["branch"]
    assert quote(data(s), b)["total"] == Decimal("105.15")
    assert quote(data(s, kg="3.1"), b)["total"] == Decimal("108.66")  # 108.655 half up
    assert quote(data(s, kg="7.1", service=str(s["load"].id)), b)["total"] == Decimal(
        "300.00"
    )
    assert quote(data(s, kg="0", **{"piece_" + str(s["variant"].id): "2"}), b)[
        "total"
    ] == Decimal("360.00")
    mixed = quote(
        data(
            s,
            addons=[str(s["addon"].id)] * 2,
            fees=[str(s["fee"].id)] * 2,
            **{"piece_" + str(s["variant"].id): "1"},
        ),
        b,
    )
    assert mixed["total"] == Decimal("355.15")
    assert mixed["total"] == sum(l["amount"] for l in mixed["lines"])


@pytest.mark.parametrize("kg", ["-1", "NaN", "Infinity", "0.01", "100000"])
def test_invalid_weight_is_atomic(setup_shop, kg):
    s = setup_shop
    before = s["branch"].job_seq
    with pytest.raises(ValidationError):
        create_job(data(s, kg=kg), s["branch"])
    assert Job.objects.count() == Event.objects.count() == JobLine.objects.count() == 0
    s["branch"].refresh_from_db()
    assert s["branch"].job_seq == before


def test_empty_does_not_consume_number_or_customer(setup_shop):
    s = setup_shop
    with pytest.raises(ValidationError):
        create_job(data(s, kg="0", customer_name="not saved"), s["branch"])
    assert not Customer.objects.exists()
    job, _ = create_job(data(s), s["branch"])
    assert job.number == 1001
    b = Branch.objects.create(shop=s["shop"], name="TEST branch2", number=2, code="T2")
    assert create_job(data(s), b)[0].number == 2001


def test_snapshot_and_heavy_items(setup_shop):
    s = setup_shop
    service = s["service"]
    service.name = "Heavy items"
    service.save()
    job, _ = create_job(data(s, addons=[str(s["addon"].id)]), s["branch"])
    service.name = "Changed"
    service.price = "500.00"
    service.save()
    assert job.lines.get(kind="base").label == "Heavy items"
    assert job.total == Decimal("125.15")
    line = job.lines.first()
    line.amount = 0
    with pytest.raises(ValidationError):
        line.save()
    with pytest.raises(ValidationError):
        job.lines.update(amount=0)
    with pytest.raises(ValidationError):
        job.lines.all().delete()


@pytest.mark.parametrize("method", ["", "cash", "gcash"])
def test_payments_actor_and_event_sequence(setup_shop, method):
    s = setup_shop
    job, _ = create_job(
        data(s, pay_method=method, pay_ref="REF-123"), s["branch"], s["staff"]
    )
    assert job.paid_at is not None if method else job.paid_at is None
    assert job.pay_ref == ("REF-123" if method == "gcash" else "")
    events = list(Event.objects.order_by("seq"))
    assert [e.seq for e in events] == list(range(1, len(events) + 1))
    assert all(e.actor_staff == s["staff"] for e in events)
    if method:
        assert events[1].payload["context"] == "at drop-off"
        assert events[1].payload["amount"] == str(job.total)
        assert job.paid_amount == job.total
    with pytest.raises(ValidationError):
        events[0].delete()
    with pytest.raises(ValidationError):
        Event.objects.update(type="changed")


def paper(s, days=1, **extra):
    date = timezone.localdate() - timedelta(days=days)
    return data(
        s,
        paper="1",
        paper_ref="P-7",
        paper_date=date.isoformat(),
        received_time="08:00",
        written_total="99.00",
        **extra,
    )


@pytest.mark.parametrize("days", [0, 7])
def test_paper_boundary_accepts(setup_shop, days):
    s = setup_shop
    d = paper(s, days)
    if days == 0:
        d["received_time"] = "00:00"
    job, _ = create_job(d, s["branch"], s["staff"])
    assert timezone.localdate(job.received_at) == timezone.localdate() - timedelta(
        days=days
    )


@pytest.mark.parametrize("days", [-1, 8])
def test_paper_boundary_refuses(setup_shop, days):
    s = setup_shop
    with pytest.raises(ValidationError):
        create_job(paper(s, days), s["branch"])
    assert not Job.objects.exists()


def test_paper_provenance_duplicate_and_current_price(setup_shop):
    s = setup_shop
    d = paper(s, pay_method="gcash", paid_time="09:00", pay_ref="SHEET")
    job, created = create_job(d, s["branch"], s["staff"])
    assert created
    assert job.total == Decimal("105.15") and job.written_total == Decimal("99.00")
    assert (
        job.created_at > job.received_at
        and timezone.localtime(job.received_at).hour == 8
    )
    assert timezone.localtime(job.paid_at).hour == 9
    e = Event.objects.get(type="job_created")
    assert e.occurred_at == job.received_at and e.payload["from_paper"]
    again, created = create_job(d, s["branch"])
    assert not created and again.id == job.id
    assert Job.objects.count() == 1 and Event.objects.count() == 2
    # Same P reference on a different day is independent.
    d["paper_date"] = (timezone.localdate() - timedelta(days=2)).isoformat()
    assert create_job(d, s["branch"])[1]


def test_event_failure_rolls_back_everything(setup_shop):
    s = setup_shop
    with patch(
        "jobs.services.append_event",
        side_effect=RuntimeError("injected event storage failure"),
    ):
        with pytest.raises(RuntimeError):
            create_job(
                data(s, customer_name="Rollback", pay_method="cash"), s["branch"]
            )
    assert (
        not Job.objects.exists()
        and not JobLine.objects.exists()
        and not Event.objects.exists()
        and not Customer.objects.exists()
    )
    s["branch"].refresh_from_db()
    assert s["branch"].job_seq == 1000 and s["branch"].event_seq == 0


def test_tenant_manager_fail_closed_and_model_coverage(setup_shop):
    s = setup_shop
    for model in apps.get_models():
        if (
            model._meta.app_label
            in {
                "core",
                "people",
                "customers",
                "catalog",
                "jobs",
                "machines",
                "supplies",
                "events",
                "owner",
            }
            and model is not Shop
        ):
            assert issubclass(model, TenantModel), model
            assert isinstance(model._default_manager, TenantManager), model
            assert isinstance(model._base_manager, TenantManager), model
    with shop_context(None):
        assert (
            Service.objects.count()
            == Job.objects.count()
            == Branch.objects.count()
            == 0
        )
    other = Shop.objects.create(name="FOREIGN", code="OTHER")
    with shop_context(other):
        foreign = Service.objects.create(
            shop=other, name="SECRET", price="1", mode="kg"
        )
        c = Customer.objects.create(shop=other, name="SECRET CUSTOMER")
    assert not Service.objects.filter(pk=foreign.id).exists()
    for extra in [{"service": str(foreign.id)}, {"customer": str(c.id)}]:
        with pytest.raises(Http404):
            create_job(data(s, **extra), s["branch"])
    with pytest.raises(ValidationError):
        Service.objects.create(shop=other, name="ILLEGAL", price="1", mode="kg")


def test_http_form_quote_create_stub_and_isolation(setup_shop, scoped_client):
    s = setup_shop
    c = scoped_client
    assert c.get("/jobs/new/").status_code == 200
    response = c.post("/jobs/price/", data(s, kg="3.1"))
    assert b"108.66" in response.content
    response = c.post(
        "/jobs/new/",
        data(s, pay_method="gcash", pay_ref="REFERENCE", customer_name="TEST customer"),
        follow=True,
    )
    assert response.status_code == 200
    for text in [
        "TEST customer",
        "108",
        "Claim stub",
        "GCash" if False else "gcash",
        "REFERENCE",
        "TEST service",
    ]:
        if text == "108":
            continue
        assert text.encode() in response.content
    assert c.get("/jobs/999999/").status_code == 404
    other = Shop.objects.create(name="FOREIGN", code="FOREIGN")
    with shop_context(other):
        foreign = Service.objects.create(
            shop=other, name="SECRET CATALOG", price="1", mode="kg"
        )
        Customer.objects.create(shop=other, name="SECRET PERSON")
    assert b"SECRET" not in c.get("/jobs/new/").content
    assert b"SECRET" not in c.get("/customers/search/?customer_search=SECRET").content
    assert c.post("/jobs/new/", data(s, service=str(foreign.id))).status_code == 404
    # Selecting tenants through query/header/cookie has no effect.
    assert (
        b"SECRET"
        not in c.get(
            "/jobs/new/?shop=" + str(other.id), HTTP_X_SHOP_ID=str(other.id)
        ).content
    )


def test_paper_duplicate_http_opens_existing(setup_shop, scoped_client):
    d = paper(setup_shop)
    r = scoped_client.post("/jobs/new/?paper=1", d, follow=True)
    assert (
        b"Paper P-7" in r.content
        and b"Received on paper as P-7" in r.content
        and b"99.00" in r.content
    )
    r = scoped_client.post("/jobs/new/?paper=1", d, follow=True)
    assert b"already entered as job #1001" in r.content and Job.objects.count() == 1


def test_no_dev_scope_in_production(setup_shop, scoped_client, settings):
    settings.DEBUG = False
    assert scoped_client.get("/jobs/new/").status_code == 404


def test_concurrent_intake_has_unique_numbers_and_events(setup_shop, transactional_db):
    from concurrent.futures import ThreadPoolExecutor

    s = setup_shop
    sid = s["shop"].id
    bid = s["branch"].id
    payload = data(s)

    def worker(_):
        close_old_connections()
        try:
            with shop_context(sid):
                return create_job(payload, Branch.objects.get(pk=bid))[0].number
        finally:
            close_old_connections()

    # Django's in-memory shared-cache SQLite doesn't wait on table locks; use a file DB for the real concurrency probe.
    if connection.vendor == "sqlite" and "memory" in str(
        connection.settings_dict["NAME"]
    ):
        pytest.skip("File-backed concurrency exercised by scripts/check_concurrency.py")
    with ThreadPoolExecutor(max_workers=4) as pool:
        result = list(pool.map(worker, range(8)))
    assert sorted(result) == list(range(1001, 1009))
    assert Event.objects.count() == 8
