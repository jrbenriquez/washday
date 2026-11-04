from datetime import timedelta
from decimal import Decimal
from io import BytesIO
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone

from catalog.models import AddOnUse, Service, SupplyType
from core.models import (
    Branch,
    JobStage,
    Machine,
    MachineCategory,
    Settings,
    Shop,
    ShopOwner,
)
from core.tenancy import shop_context
from jobs.models import JobLine
from jobs.services import append_event, create_job
from machines.models import Load
from supplies.models import SupplyRequest


@pytest.fixture
def own(setup_shop):
    user = get_user_model().objects.create_user(
        username="workspace-owner", email="workspace@example.invalid"
    )
    ShopOwner.objects.create(shop=setup_shop["shop"], user=user, email=user.email)
    client = Client()
    client.force_login(user, backend="django.contrib.auth.backends.ModelBackend")
    return client, setup_shop


def new_job(s, **extra):
    return create_job(
        {"service": str(s["service"].id), "kg": "3", **extra}, s["branch"], s["staff"]
    )[0]


def test_owner_dashboard_uses_collections_and_received_dates(own):
    c, s = own
    paid = new_job(s, pay_method="cash")
    new_job(s)
    append_event(
        s["branch"],
        "self_service_started",
        {"amount": "150.50", "method": "gcash"},
        timezone.now(),
        s["staff"],
    )
    append_event(
        s["branch"],
        "payment_recorded",
        {"amount": "999", "method": "cash"},
        timezone.now() - timedelta(days=1),
        s["staff"],
    )
    r = c.get("/owner/dashboard/")
    assert r.status_code == 200
    assert r.context["sales"] == {
        "cash": paid.total,
        "gcash": Decimal("150.50"),
        "total": paid.total + Decimal("150.50"),
    }
    assert r.context["received"] == 2
    assert r.context["kilos"] == Decimal("6")
    other = Branch.objects.create(shop=s["shop"], name="Empty", code="EMPTY", number=2)
    r = c.get("/owner/dashboard/", {"branch": other.pk})
    assert r.context["received"] == 0 and r.context["sales"]["total"] == 0
    assert c.get("/owner/dashboard/?branch=malformed").status_code == 404


def test_owner_routes_require_owner_and_isolate_other_shops(own):
    c, s = own
    paths = [
        "/owner/dashboard/",
        "/owner/live/",
        "/owner/staff/",
        "/owner/machines/",
        "/owner/settings/",
        "/owner/reports/sales.xlsx",
    ]
    for path in paths:
        assert Client().get(path).status_code == 302
        assert c.get(path).status_code == 200
    foreign = Shop.objects.create(name="Foreign", code="FOREIGN")
    with shop_context(foreign):
        b = Branch.objects.create(
            shop=foreign, name="Foreign branch", code="F", number=1
        )
        svc = Service.objects.create(
            shop=foreign, name="Foreign service", mode="kg", price=100
        )
    for path in [
        f"/owner/live/?branch={b.pk}",
        f"/owner/dashboard/?branch={b.pk}",
        f"/owner/counts/{b.pk}/",
        f"/owner/edit/service/{svc.pk}/",
    ]:
        assert c.get(path).status_code == 404
    assert (
        c.post(f"/owner/edit/service/{svc.pk}/", {"action": "archive"}).status_code
        == 404
    )
    assert (
        c.post(
            "/owner/edit/machine/", {"branch": b.pk, "category": "", "label": "Foreign"}
        ).status_code
        == 422
    )
    csrf = Client(enforce_csrf_checks=True)
    csrf.cookies["sessionid"] = c.cookies["sessionid"].value
    assert csrf.post("/owner/operations/", {}).status_code == 403


def test_catalog_edits_preserve_job_prices_and_archive_restore(own):
    c, s = own
    job = new_job(s)
    lines = list(job.lines.values_list("label", "amount"))
    url = f"/owner/edit/service/{s['service'].pk}/"
    assert (
        c.post(url, {"name": "Changed", "mode": "load", "price": "900.50"}).status_code
        == 302
    )
    assert list(JobLine.objects.filter(job=job).values_list("label", "amount")) == lines
    assert c.post(url, {"action": "archive"}).status_code == 302
    s["service"].refresh_from_db()
    assert s["service"].archived_at
    assert c.post(url, {"action": "archive"}).status_code == 302
    s["service"].refresh_from_db()
    assert not s["service"].archived_at
    assert c.post(url, {"name": "Bad", "mode": "kg", "price": "-1"}).status_code == 422


def test_settings_and_active_load_guards(own):
    c, s = own
    assert (
        c.post(
            "/owner/operations/",
            {"min_kg": "0", "kg_per_load": "0", "check_after_min": "90"},
        ).status_code
        == 422
    )
    assert (
        c.post(
            "/owner/operations/",
            {
                "min_kg": "4",
                "kg_per_load": "8",
                "check_after_min": "60",
                "staff_can_add_supply": "on",
            },
        ).status_code
        == 302
    )
    config = Settings.objects.get()
    assert config.kg_per_load == 8 and config.staff_can_add_supply
    cat = MachineCategory.objects.create(
        shop=s["shop"], name="Washer", label_prefix="W"
    )
    machine = Machine.objects.create(
        shop=s["shop"], branch=s["branch"], category=cat, label="W1"
    )
    load = Load.objects.create(
        shop=s["shop"], branch=s["branch"], machine=machine, started_at=timezone.now()
    )
    url = f"/owner/edit/machine/{machine.pk}/"
    assert c.post(url, {"action": "archive"}).status_code == 422
    assert (
        c.post(
            url,
            {
                "branch": s["branch"].pk,
                "category": cat.pk,
                "label": "W1",
                "out_of_service": "on",
            },
        ).status_code
        == 422
    )
    s["branch"].simple_mode = False
    s["branch"].save(update_fields=["simple_mode"])
    c.post(f"/owner/branches/{s['branch'].pk}/mode/", {"simple_mode": "1"})
    s["branch"].refresh_from_db()
    assert not s["branch"].simple_mode
    assert (
        c.post(f"/owner/edit/category/{cat.pk}/", {"action": "archive"}).status_code
        == 422
    )
    load.ended_at = timezone.now()
    load.save(update_fields=["ended_at"])
    assert c.post(url, {"action": "archive"}).status_code == 302


def test_stage_endpoints_and_active_jobs_are_protected(own):
    c, s = own
    job = new_job(s)
    for stage in JobStage.objects.filter(is_first=True) | JobStage.objects.filter(
        is_last=True
    ):
        assert (
            c.post(f"/owner/edit/stage/{stage.pk}/", {"action": "archive"}).status_code
            == 422
        )
    middle = JobStage.objects.get(name="Folding")
    job.status = middle
    job.save(update_fields=["status"])
    assert (
        c.post(f"/owner/edit/stage/{middle.pk}/", {"action": "archive"}).status_code
        == 422
    )
    r = c.post(
        f"/owner/edit/stage/{middle.pk}/",
        {"name": "Folding", "sort_order": "3", "show_in_simple_mode": "on"},
    )
    assert r.status_code == 302


def test_supply_request_fulfilment_is_atomic_and_tenant_scoped(own):
    c, s = own
    req = SupplyRequest.objects.create(
        shop=s["shop"], branch=s["branch"], name="Bleach"
    )
    url = f"/owner/edit/supply/?request={req.pk}"
    data = {
        "name": "Bleach",
        "unit": "ml",
        "low_level": "2",
        "per_washer_load": "5",
        "per_packed_job": "0",
    }
    assert c.post(url, {**data, "low_level": "-1"}).status_code == 422
    req.refresh_from_db()
    assert (
        req.status == "open" and not SupplyType.objects.filter(name="Bleach").exists()
    )
    assert c.post(url, data).status_code == 302
    req.refresh_from_db()
    assert (
        req.status == "fulfilled" and SupplyType.objects.filter(name="Bleach").exists()
    )
    supply = SupplyType.objects.get(name="Bleach")
    assert (
        c.post(
            "/owner/edit/recipe/",
            {"addon": s["addon"].pk, "supply_type": supply.pk, "qty": "2.5"},
        ).status_code
        == 302
    )
    assert AddOnUse.objects.get().qty == Decimal("2.5")


def test_excel_contains_only_selected_branch_and_dates(own):
    c, s = own
    job = new_job(s, pay_method="cash")
    r = c.get("/owner/reports/sales.xlsx", {"branch": s["branch"].pk})
    assert r.status_code == 200
    with ZipFile(BytesIO(r.content)) as z:
        for file in z.namelist():
            ET.fromstring(z.read(file))
        sheet = z.read("xl/worksheets/sheet1.xml").decode()
        assert s["branch"].name in sheet and str(job.total) in sheet
    assert c.get("/owner/reports/sales.xlsx?start=bad").status_code == 422
    assert (
        c.get("/owner/reports/sales.xlsx?start=2026-11-04&end=2026-01-01").status_code
        == 422
    )


def test_owner_live_has_no_staff_write_controls(own):
    c, s = own
    new_job(s)
    s["branch"].simple_mode = False
    s["branch"].save(update_fields=["simple_mode"])
    r = c.get("/owner/live/")
    assert r.status_code == 200
    text = r.content.decode()
    for path in ["/advance/", "/claim/", "/unload/", "/start/"]:
        assert path not in text
    assert "Walk-in" in text


def test_stage_insert_archive_restore_keeps_order_and_endpoints(own):
    c, s = own
    assert (
        c.post("/owner/edit/stage/", {"name": "Ironing", "sort_order": 3}).status_code
        == 302
    )
    stage = JobStage.objects.get(name="Ironing")
    active = list(JobStage.objects.filter(archived_at=None).order_by("sort_order"))
    assert active[0].is_first and active[-1].is_last
    assert [x.sort_order for x in active] == list(range(6))
    url = f"/owner/edit/stage/{stage.pk}/"
    assert c.post(url, {"action": "archive"}).status_code == 302
    assert (
        c.post("/owner/edit/stage/", {"name": "Bagging", "sort_order": 3}).status_code
        == 302
    )
    assert c.post(url, {"action": "archive"}).status_code == 302
    active = list(JobStage.objects.filter(archived_at=None).order_by("sort_order"))
    assert active[0].is_first and active[-1].is_last
    assert [x.sort_order for x in active] == list(range(7))


def test_staff_transfer_requires_new_branch_unique_pin(own):
    from people.services import save_staff

    c, s = own
    person, _ = save_staff(s["branch"], "Transfer staff", "1234")
    target = Branch.objects.create(
        shop=s["shop"], name="Destination", code="DEST", number=2
    )
    other, _ = save_staff(target, "Other staff", "5678")
    url = f"/owner/staff/{person.pk}/"
    data = {"name": person.name, "active": "1", "branch": target.pk}
    assert c.post(url, data).status_code == 422
    assert c.post(url, {**data, "pin": "5678"}).status_code == 422
    assert c.post(url, {**data, "pin": "4321"}).status_code == 200
    person.refresh_from_db()
    assert person.branch_id == target.pk


def test_staff_management_only_appears_on_staff_page(own):
    c, s = own
    access = c.get("/owner/")
    assert access.status_code == 200
    assert b'action="/owner/staff/' not in access.content
    assert s["staff"].name.encode() not in access.content
    assert b'action="/owner/devices/new/"' in access.content
    assert b'action="/owner/pin-rules/"' not in access.content
    assert b'name="opening_time"' not in access.content

    staff = c.get("/owner/staff/")
    assert staff.status_code == 200
    assert staff.content.count(b'action="/owner/staff/new/"') == 1
    assert staff.content.count(
        f'action="/owner/staff/{s["staff"].pk}/"'.encode()
    ) == 1
    assert b"Generate a fresh PIN" in staff.content
    assert "devices" not in staff.context


def test_staff_page_filters_branches_and_includes_inactive_staff(own):
    from people.models import Staff

    c, s = own
    branch = Branch.objects.create(
        shop=s["shop"], name="Second branch", code="SECOND", number=2
    )
    person = Staff.objects.create(
        shop=s["shop"], branch=branch, name="Inactive colleague", active=False,
        pin_hash="!",
    )
    all_staff = c.get("/owner/staff/")
    assert {p.pk for p in all_staff.context["people"]} == {s["staff"].pk, person.pk}
    selected = c.get("/owner/staff/", {"branch": branch.pk})
    assert [p.pk for p in selected.context["people"]] == [person.pk]
    assert selected.context["selected_branch"] == branch
    assert f'value="{branch.pk}" selected'.encode() in selected.content
    assert b"Inactive" in selected.content


@pytest.mark.parametrize("pin", ["6789", ""])
def test_staff_creation_returns_once_only_pin_and_links_to_staff(own, pin):
    from django.contrib.auth.hashers import check_password
    from people.models import Staff

    c, s = own
    response = c.post("/owner/staff/new/", {
        "branch": s["branch"].pk, "name": "New colleague", "pin": pin,
    })
    assert response.status_code == 200
    person = Staff.objects.get(name="New colleague")
    shown_pin = response.context["shown_pin"]
    assert len(shown_pin) == 4 and shown_pin.isdigit()
    assert check_password(shown_pin, person.pin_hash)
    if pin:
        assert shown_pin == pin
    assert b'href="/owner/staff/">Back to staff</a>' in response.content
    assert "no-store" in response.headers["Cache-Control"]
    staff = c.get("/owner/staff/")
    assert b"New colleague" in staff.content
    assert shown_pin.encode() not in staff.content


@pytest.mark.parametrize("pin", ["12", "1234"])
def test_staff_creation_validation_returns_staff_form_with_branch(own, pin):
    from people.services import save_staff
    from people.models import Staff

    c, s = own
    branch = Branch.objects.create(
        shop=s["shop"], name="Second branch", code="SECOND", number=2
    )
    save_staff(branch, "Existing colleague", "1234")
    before = Staff.objects.count()
    response = c.post("/owner/staff/new/", {
        "branch": branch.pk, "name": "Unsaved colleague", "pin": pin,
    })
    assert response.status_code == 422
    assert response.templates[0].name == "owner/staff.html"
    assert response.context["staff_form"].errors
    assert b'value="Unsaved colleague"' in response.content
    assert f'value="{branch.pk}" selected'.encode() in response.content
    assert Staff.objects.count() == before
    assert {p.branch_id for p in response.context["people"]} == {branch.pk}


def test_staff_edit_without_pin_returns_to_staff(own):
    c, s = own
    person = s["staff"]
    original_hash = person.pin_hash
    response = c.post(f"/owner/staff/{person.pk}/", {
        "name": "Renamed colleague", "active": "1", "branch": person.branch_id,
    })
    assert response.status_code == 302 and response.url == "/owner/staff/"
    person.refresh_from_db()
    assert person.name == "Renamed colleague" and person.active
    assert person.pin_hash == original_hash
    response = c.post(f"/owner/staff/{person.pk}/", {"name": person.name})
    assert response.url == "/owner/staff/"
    person.refresh_from_db()
    assert not person.active


@pytest.mark.parametrize("change", [{"pin": "6789"}, {"generate": "1"}])
def test_staff_pin_reset_returns_to_staff_and_is_shown_once(own, change):
    from django.contrib.auth.hashers import check_password
    from people.services import save_staff

    c, s = own
    person, _ = save_staff(s["branch"], "PIN colleague", "1234")
    response = c.post(f"/owner/staff/{person.pk}/", {
        "name": person.name, "active": "1", "branch": person.branch_id, **change,
    })
    assert response.status_code == 200
    person.refresh_from_db()
    shown_pin = response.context["shown_pin"]
    assert shown_pin != "1234" and check_password(shown_pin, person.pin_hash)
    assert b'href="/owner/staff/">Back to staff</a>' in response.content
    assert "no-store" in response.headers["Cache-Control"]
    assert shown_pin.encode() not in c.get("/owner/staff/").content


def test_staff_edit_validation_stays_on_staff_and_does_not_save(own):
    c, s = own
    person = s["staff"]
    response = c.post(f"/owner/staff/{person.pk}/", {
        "name": "Unsaved rename", "active": "1", "pin": "12",
    })
    assert response.status_code == 422
    assert response.templates[0].name == "owner/staff.html"
    assert b'role="alert">A PIN must be exactly four digits.' in response.content
    assert f'action="/owner/staff/{person.pk}/"'.encode() in response.content
    person.refresh_from_db()
    assert person.name == "TEST staff" and person.pin_hash == "!"


def test_pin_rules_only_appear_in_settings_and_save_returns_there(own):
    c, s = own
    for path in ["/owner/", "/owner/staff/"]:
        response = c.get(path)
        assert b'action="/owner/pin-rules/"' not in response.content
        assert "policy_form" not in response.context
    response = c.get("/owner/settings/")
    assert response.content.count(b'action="/owner/pin-rules/"') == 1
    assert b"these prompts apply to shared devices" in response.content
    response = c.post("/owner/pin-rules/", {
        "pin_enabled": "on", "pin_actions": ["payment", "claim"],
    })
    assert response.status_code == 302 and response.url == "/owner/settings/"
    config = Settings.objects.get(shop=s["shop"])
    assert config.pin_enabled and config.pin_actions == ["payment", "claim"]
    response = c.get(response.url)
    assert response.context["policy_form"].initial["pin_actions"] == ["payment", "claim"]


def test_invalid_pin_rules_return_to_settings_without_changing_policy(own):
    c, s = own
    config = Settings.objects.get(shop=s["shop"])
    before = (config.pin_enabled, config.pin_actions, config.version)
    response = c.post("/owner/pin-rules/", {"pin_actions": ["invalid-action"]})
    assert response.status_code == 422
    assert response.templates[0].name == "owner/settings.html"
    assert response.context["policy_form"].errors
    assert b"invalid-action" in response.content
    assert b'action="/owner/pin-rules/"' in response.content
    assert "operations_form" in response.context and "branding_form" in response.context
    assert b'action="/owner/settings/" enctype="multipart/form-data"' in response.content
    config.refresh_from_db()
    assert (config.pin_enabled, config.pin_actions, config.version) == before
