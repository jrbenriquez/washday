from datetime import time
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone

from core.models import Branch, Machine, MachineCategory, Settings, Shop, ShopOwner
from core.tenancy import shop_context
from events.models import Event
from machines.models import Load


@pytest.fixture
def own(setup_shop):
    user = get_user_model().objects.create_user(
        username="branch-owner", email="branches@example.invalid"
    )
    ShopOwner.objects.create(shop=setup_shop["shop"], user=user, email=user.email)
    c = Client()
    c.force_login(user, backend="django.contrib.auth.backends.ModelBackend")
    return c, setup_shop


def details(**extra):
    return {
        "name": "North branch",
        "code": "NORTH",
        "opening_time": "08:00",
        "closing_time": "20:00",
        "simple_mode": "on",
        **extra,
    }


def test_navigation_live_and_single_settings_home(own):
    c, s = own
    for path in ("/owner/branches/", "/owner/live/"):
        r = c.get(path, {"branch": s["branch"].pk})
        assert r.status_code == 200
        assert r.templates[0].name == "owner/live.html"
        assert b">Branches</a>" in r.content
        assert b'aria-label="Branch views"' in r.content
        assert b"every 20s" in r.content and b"Watch only." in r.content
        assert f'/owner/branches/{s["branch"].pk}/edit/'.encode() in r.content
        assert b"Edit branch</a>" in r.content
    r = c.get("/owner/branches/manage/")
    assert s["branch"].name.encode() in r.content and b"Add branch</a>" in r.content
    for path in ("/owner/settings/", "/owner/"):
        r = c.get(path)
        assert b'name="simple_mode"' not in r.content
        assert b'name="opening_time"' not in r.content
    assert b"/owner/branches/manage/" in c.get("/owner/settings/").content


def test_add_defaults_allocation_version_and_event(own):
    c, s = own
    r = c.get("/owner/branches/new/")
    assert r.context["form"]["simple_mode"].value() is True
    assert r.context["form"]["connection_mode"].value() == "direct"
    # Sparse numbering is preserved; no existing counter is overwritten.
    Branch.objects.create(shop=s["shop"], name="Sparse", code="SPARSE", number=7)
    # Catalog signals now advance the version for fixture configuration changes too.
    version = Settings.objects.get().version
    r = c.post("/owner/branches/new/", details(number="1", shop="forged", job_seq="99"))
    assert r.status_code == 302 and r.url == "/owner/branches/manage/"
    b = Branch.objects.get(code="NORTH")
    assert (b.number, b.job_seq, b.mode, b.simple_mode) == (8, 8000, "direct", True)
    assert b.shop_id == s["shop"].pk
    assert b.opening_time == time(8) and b.closing_time == time(20)
    assert Settings.objects.get().version == version + 1
    event = Event.objects.get(branch=b, type="branch_created")
    assert event.payload["owner"] == "branches@example.invalid"
    assert c.get("/owner/branches/", {"branch": b.pk}).status_code == 200
    # New branches appear in existing staff/device branch pickers.
    assert str(b.pk).encode() in c.get("/owner/staff/").content
    assert str(b.pk).encode() in c.get("/owner/").content


def test_edit_preserves_identity_counters_and_allows_full_workflow(own):
    c, s = own
    b = s["branch"]
    Branch.objects.filter(pk=b.pk).update(job_seq=1392, event_seq=12)
    r = c.post(
        f"/owner/branches/{b.pk}/edit/",
        details(simple_mode="", number="9", job_seq="0"),
    )
    assert r.status_code == 302
    b.refresh_from_db()
    assert (b.name, b.code, b.number, b.job_seq, b.event_seq, b.simple_mode) == (
        "North branch",
        "NORTH",
        1,
        1392,
        13,
        False,
    )
    assert Event.objects.filter(branch=b, type="branch_updated").count() == 1


@pytest.mark.parametrize(
    "overrides",
    [
        {"name": ""},
        {"code": ""},
        {"opening_time": "25:00"},
        {"closing_time": ""},
        {"code": "test"},
        {"mode": "hub"},
        {"connection_mode": "hub"},
    ],
)
def test_invalid_create_preserves_values_and_has_no_partial_writes(own, overrides):
    c, s = own
    count, version, events = (
        Branch.objects.count(),
        Settings.objects.get().version,
        Event.objects.count(),
    )
    r = c.post("/owner/branches/new/", details(**overrides))
    assert r.status_code == 422
    assert r.context["form"].is_bound and r.context["form"].errors
    assert r.context["form"]["code"].value() == overrides.get("code", "NORTH")
    assert (
        Branch.objects.count(),
        Settings.objects.get().version,
        Event.objects.count(),
    ) == (count, version, events)


def test_edit_unique_code_and_open_load_guard_are_atomic(own):
    c, s = own
    b = s["branch"]
    b.simple_mode = False
    b.save()
    other = Branch.objects.create(shop=s["shop"], name="North", code="NORTH", number=2)
    category = MachineCategory.objects.create(
        shop=s["shop"], name="Washers", label_prefix="W"
    )
    machine = Machine.objects.create(
        shop=s["shop"], branch=b, category=category, label="W1"
    )
    load = Load.objects.create(
        shop=s["shop"], branch=b, machine=machine, started_at=timezone.now()
    )
    url = f"/owner/branches/{b.pk}/edit/"
    version = Settings.objects.get().version
    assert c.post(url, details()).status_code == 422
    assert c.post(url, details(code="UNIQUE")).status_code == 422
    b.refresh_from_db()
    assert not b.simple_mode and b.code == "TEST"
    assert Settings.objects.get().version == version and Event.objects.count() == 0
    load.ended_at = timezone.now()
    load.save()
    assert c.post(url, details(code="UNIQUE")).status_code == 302
    b.refresh_from_db()
    assert b.simple_mode
    assert Branch.objects.get(pk=other.pk).code == "NORTH"


def test_audit_failure_rolls_back_branch_and_settings(own):
    c, s = own
    version = Settings.objects.get().version
    from django.core.exceptions import ValidationError

    with patch(
        "owner.workspace.audit", side_effect=ValidationError("Audit unavailable")
    ):
        assert c.post("/owner/branches/new/", details()).status_code == 422
        assert (
            c.post(f'/owner/branches/{s["branch"].pk}/edit/', details()).status_code
            == 422
        )
    assert Branch.objects.count() == 1 and Settings.objects.get().version == version
    s["branch"].refresh_from_db()
    assert s["branch"].code == "TEST"


def test_owner_tenant_csrf_and_method_boundaries(own):
    c, s = own
    foreign = Shop.objects.create(name="Foreign", code="FOREIGN")
    with shop_context(foreign):
        b = Branch.objects.create(
            shop=foreign, name="Private foreign branch", code="NORTH", number=1
        )
    for path in (
        "/owner/branches/",
        "/owner/branches/manage/",
        "/owner/branches/new/",
        f'/owner/branches/{s["branch"].pk}/edit/',
    ):
        assert Client().get(path).status_code == 302
        assert Client().post(path, details()).status_code == 302
    assert c.get(f"/owner/branches/{b.pk}/edit/").status_code == 404
    assert c.post(f"/owner/branches/{b.pk}/edit/", details()).status_code == 404
    assert c.get("/owner/branches/", {"branch": b.pk}).status_code == 404
    assert c.get("/owner/branches/", {"branch": "broken"}).status_code == 404
    assert b.name.encode() not in c.get("/owner/branches/manage/").content
    # Code and internal number are unique within a shop, not across shops.
    assert c.post("/owner/branches/new/", details()).status_code == 302
    csrf = Client(enforce_csrf_checks=True)
    csrf.cookies["sessionid"] = c.cookies["sessionid"].value
    assert csrf.post("/owner/branches/new/", details()).status_code == 403
    assert c.post("/owner/branches/manage/").status_code == 405


def test_first_branch_empty_states_and_allocation(own):
    c, s = own
    # A separate empty shop exercises max(NULL) allocation without removing historical records.
    empty = Shop.objects.create(name="Empty shop", code="EMPTY", onboarding_completed_at=timezone.now())
    ShopOwner.objects.filter(user__username="branch-owner").update(shop=empty)
    with shop_context(empty):
        Settings.objects.create(shop=empty)
    assert b"No branches yet" in c.get("/owner/branches/").content
    assert b"No branches yet" in c.get("/owner/branches/manage/").content
    assert c.post("/owner/branches/new/", details()).status_code == 302
    with shop_context(empty):
        b = Branch.objects.get()
        assert (b.number, b.job_seq) == (1, 1000)
