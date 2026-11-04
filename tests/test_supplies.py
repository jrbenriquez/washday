from decimal import Decimal
from datetime import timedelta
from unittest.mock import patch
import pytest
from django.core.exceptions import ValidationError, PermissionDenied
from django.http import Http404
from django.utils import timezone
from core.models import Settings, JobStage, Branch, Shop
from core.tenancy import shop_context
from catalog.models import SupplyType, AddOnUse
from supplies.models import StockEntry, StockCount, StockCountLine, SupplyRequest
from supplies.services import balance, receive, count_stock, request_supply, add_type
from jobs.services import create_job
from jobs.transitions import advance, override
from machines.services import start_for_job, self_service


@pytest.fixture
def stock_setup(setup_shop):
    s = setup_shop
    detergent = SupplyType.objects.create(
        shop=s["shop"], name="Detergent", unit="cup", low_level=3, per_washer_load="0.5"
    )
    bag = SupplyType.objects.create(
        shop=s["shop"], name="Bag", unit="piece", low_level=5, per_packed_job=1
    )
    AddOnUse.objects.create(
        shop=s["shop"], addon=s["addon"], supply_type=detergent, qty="0.25"
    )
    receive(s["branch"], detergent.id, "10", s["staff"])
    receive(s["branch"], bag.id, "20", s["staff"])
    return {**s, "detergent": detergent, "bag": bag}


def create(s, **extra):
    return create_job(
        {"kg": "2", "service": str(s["service"].id), **extra}, s["branch"], s["staff"]
    )[0]


def ready(s, j):
    return advance(s["branch"], j.number, j.status_id, s["staff"])


def test_addon_and_first_ready_atomic_once(stock_setup):
    s = stock_setup
    j = create(s, addons=[str(s["addon"].id)] * 2)
    assert balance(s["branch"], s["detergent"]) == Decimal("9.75")
    j = ready(s, j)
    assert balance(s["branch"], s["bag"]) == 19
    first = JobStage.objects.get(is_first=True)
    j = override(s["branch"], j.number, j.status_id, first.id, staff=s["staff"])
    j = ready(s, j)
    assert balance(s["branch"], s["bag"]) == 19
    assert StockEntry.objects.filter(reason="packed_job", job=j).count() == 1
    assert StockEntry.objects.filter(reason="addon", job=j).count() == 1


def test_archived_recipe_skipped_and_paper_simple_no_washer(stock_setup):
    s = stock_setup
    s["detergent"].archived_at = timezone.now()
    s["detergent"].save(update_fields=["archived_at"])
    day = (timezone.localdate() - timedelta(days=1)).isoformat()
    j = create(
        s,
        addons=[str(s["addon"].id)],
        paper="1",
        paper_ref="P-1",
        paper_date=day,
        received_time="08:00",
        written_total="10",
    )
    ready(s, j)
    assert (
        balance(s["branch"], s["detergent"]) == 10
        and balance(s["branch"], s["bag"]) == 19
    )
    assert not StockEntry.objects.filter(reason="washer_load").exists()
    assert StockEntry.objects.filter(supply_type=s["detergent"]).exists()


def test_load_category_deductions_and_selfservice(stock_setup):
    from core.models import Machine, MachineCategory

    s = stock_setup
    b = s["branch"]
    b.simple_mode = False
    b.save(update_fields=["simple_mode"])
    washer = MachineCategory.objects.create(
        shop=s["shop"], name="Washer", label_prefix="W", uses_wash_supplies=True
    )
    dryer = MachineCategory.objects.create(
        shop=s["shop"], name="Dryer", label_prefix="D"
    )
    w = Machine.objects.create(shop=s["shop"], branch=b, category=washer, label="W1")
    w2 = Machine.objects.create(shop=s["shop"], branch=b, category=washer, label="W2")
    d = Machine.objects.create(shop=s["shop"], branch=b, category=dryer, label="D1")
    wash = JobStage.objects.get(name="Washing")
    wash.machine_category = washer
    wash.save()
    dry = JobStage.objects.get(name="Drying")
    dry.machine_category = dryer
    dry.save()
    j = create(s)
    l = start_for_job(b, j.number, j.status_id, wash.id, w.id, s["staff"])
    assert balance(b, s["detergent"]) == Decimal("9.5")
    j.refresh_from_db()
    start_for_job(b, j.number, j.status_id, dry.id, d.id, s["staff"])
    assert balance(b, s["detergent"]) == Decimal("9.5")
    self_service(b, w2.id, s["load"].id, "cash", s["staff"])
    assert balance(b, s["detergent"]) == 9
    assert StockEntry.objects.get(load=l).reason == "washer_load"


def test_receipts_positive_and_rollback_preserves_job_and_stock(stock_setup):
    s = stock_setup
    before = balance(s["branch"], s["detergent"])
    for raw in ["0", "-1", "NaN", "1.0001"]:
        with pytest.raises(ValidationError):
            receive(s["branch"], s["detergent"].id, raw)
    assert balance(s["branch"], s["detergent"]) == before
    with patch(
        "supplies.services.append_event", side_effect=RuntimeError("ledger event fail")
    ):
        with pytest.raises(RuntimeError):
            create(s, addons=[str(s["addon"].id)])
    from jobs.models import Job

    assert not Job.objects.exists() and balance(s["branch"], s["detergent"]) == before


def test_full_partial_zero_variance_and_immutability(stock_setup):
    s = stock_setup
    b = s["branch"]
    d = s["detergent"]
    bag = s["bag"]
    full = count_stock(
        b, {"count_" + str(d.id): "7", "count_" + str(bag.id): "20"}, s["staff"]
    )
    assert balance(b, d) == 7 and balance(b, bag) == 20
    assert full.lines.get(supply_type=d).variance == -3
    assert StockEntry.objects.filter(reason="count_adjust").count() == 1
    partial = count_stock(
        b,
        {"partial": "1", "count_" + str(d.id): "9", "count_" + str(bag.id): ""},
        s["staff"],
    )
    assert (
        partial.partial
        and partial.lines.count() == 1
        and balance(b, bag) == 20
        and balance(b, d) == 9
    )
    for obj in [full, full.lines.first(), StockEntry.objects.first()]:
        with pytest.raises(ValidationError):
            obj.delete()
        with pytest.raises(ValidationError):
            obj.save()
    with pytest.raises(ValidationError):
        StockCount.objects.update(partial=True)
    with pytest.raises(ValidationError):
        StockCountLine.objects.all().delete()
    with pytest.raises(ValidationError):
        count_stock(b, {"count_" + str(d.id): "1"}, s["staff"])
    assert StockCount.objects.count() == 2


@pytest.mark.parametrize(
    "variance,css",
    [
        (0, "plain"),
        (1, "warn"),
        (-1, "warn"),
        (3, "warn"),
        (-3, "warn"),
        (4, "crit"),
        (-4, "crit"),
    ],
)
def test_variance_thresholds_and_low(stock_setup, scoped_client, variance, css):
    s = stock_setup
    d = s["detergent"]
    count_stock(
        s["branch"],
        {"partial": "1", "count_" + str(d.id): str(10 + variance)},
        s["staff"],
    )
    r = scoped_client.get("/supplies/")
    assert f"pill {css}".encode() in r.content and b"Count variance" in r.content
    count_stock(s["branch"], {"partial": "1", "count_" + str(d.id): "3"})
    assert b">Low<" in scoped_client.get("/supplies/").content


def test_requests_lock_unlock_case_name_and_archived_restore(
    stock_setup, scoped_client
):
    s = stock_setup
    b = s["branch"]
    payload = {
        "name": "New",
        "unit": "cup",
        "low_level": "1",
        "per_washer_load": "0.1",
        "per_packed_job": "0",
    }
    with pytest.raises(PermissionDenied):
        add_type(b, payload)
    assert scoped_client.post("/supplies/types/new/", payload).status_code == 403
    request_supply(b, "New", "Please add", s["staff"])
    assert SupplyRequest.objects.get().status == "open"
    settings = Settings.objects.get()
    settings.staff_can_add_supply = True
    settings.save(update_fields=["staff_can_add_supply"])
    new = add_type(b, payload, s["staff"])
    assert new.name == "New"
    with pytest.raises(ValidationError):
        add_type(b, {**payload, "name": " nEW "})
    new.archived_at = timezone.now()
    new.save(update_fields=["archived_at"])
    with pytest.raises(ValidationError, match="restored"):
        add_type(b, payload)
    assert b"New supply requested" in scoped_client.get("/jobs/?view=history").content


def test_foreign_supply_requests_and_branch_balance_isolation(
    stock_setup, scoped_client
):
    s = stock_setup
    other = Shop.objects.create(code="FOREIGN", name="SECRET")
    with shop_context(other):
        foreign = SupplyType.objects.create(shop=other, name="SECRET", unit="x")
    with pytest.raises(Http404):
        receive(s["branch"], foreign.id, "1")
    with pytest.raises(Http404):
        count_stock(s["branch"], {"partial": "1", "count_" + str(foreign.id): "1"})
    assert b"SECRET" not in scoped_client.get("/supplies/").content
    b = Branch.objects.create(shop=s["shop"], name="Other", number=2, code="Other")
    receive(b, s["detergent"].id, "100")
    assert balance(s["branch"], s["detergent"]) == 10


def test_pagination_and_count_http(stock_setup, scoped_client):
    s = stock_setup
    for i in range(12):
        receive(s["branch"], s["detergent"].id, "1")
    r = scoped_client.get("/supplies/")
    assert b">Older<" in r.content
    assert len(r.context["entries"]) == 10
    r = scoped_client.get("/supplies/?page=2")
    assert b">Newer<" in r.content
    r = scoped_client.post(
        "/supplies/count/", {"count_" + str(s["detergent"].id): "1"}, follow=True
    )
    assert r.status_code == 422 and b"full count needs every" in r.content
    r = scoped_client.post(
        "/supplies/count/",
        {"partial": "1", "count_" + str(s["detergent"].id): "1"},
        follow=True,
    )
    assert r.status_code == 200 and b"Stock count saved" in r.content
