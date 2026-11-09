from decimal import Decimal
from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client

from catalog.models import PieceItem, PieceVariant, Service
from core.models import Branch, Settings, Shop, ShopOwner
from core.tenancy import shop_context

pytestmark = pytest.mark.django_db


def test_seeded_demo_shop_is_already_configured(settings):
    settings.DEBUG = True
    call_command("seed_demo", stdout=StringIO())
    assert Shop.objects.get(code="DEV-ONLY").onboarding_completed_at


@pytest.fixture
def new_owner(client):
    shop = Shop.objects.create(name="New laundry", code="NEW")
    user = get_user_model().objects.create_user(username="new-owner")
    with shop_context(shop):
        ShopOwner.objects.create(shop=shop, user=user, email="owner@example.invalid")
    client.force_login(user, backend="django.contrib.auth.backends.ModelBackend")
    return client, shop


def payload():
    return {
        "services-TOTAL_FORMS": "2", "services-INITIAL_FORMS": "2",
        "services-0-name": "Wash + Dry + Fold", "services-0-mode": "kg", "services-0-price": "35",
        "services-1-name": "Wash + Dry", "services-1-mode": "load", "services-1-price": "150",
        "pieces-TOTAL_FORMS": "1", "pieces-INITIAL_FORMS": "1",
        "pieces-0-name": "Plastic", "pieces-0-label": "Each", "pieces-0-price": "5",
        "min_kg": "3", "kg_per_load": "7",
    }


def test_first_owner_redirect_defaults_and_access_control(new_owner):
    client, shop = new_owner
    for path in ("/owner/", "/owner/dashboard/", "/owner/settings/", "/owner/login/"):
        assert client.get(path).url == "/owner/onboarding/"
    page = client.get("/owner/onboarding/")
    assert page.status_code == 200
    assert page.context["services"].forms[0].initial["name"] == "Wash + Dry + Fold"
    assert page.context["services"].forms[1].initial["name"] == "Wash + Dry"
    assert page.context["pieces"].forms[0].initial["name"] == "Plastic"
    assert not page.context["services"].forms[0].initial.get("price")
    assert Client().get("/owner/onboarding/").url == "/owner/login/"
    csrf = Client(enforce_csrf_checks=True)
    csrf.cookies["sessionid"] = client.cookies["sessionid"].value
    assert csrf.post("/owner/onboarding/", payload()).status_code == 403


def test_save_once_and_device_prefill(new_owner):
    client, shop = new_owner
    result = client.post("/owner/onboarding/", payload())
    assert result.url == "/owner/onboarding/branch/"
    shop.refresh_from_db()
    assert shop.onboarding_catalog_saved_at
    assert not shop.onboarding_completed_at
    assert not Branch.unscoped.filter(shop=shop).exists()
    assert client.get("/owner/dashboard/").url == result.url
    assert client.get("/owner/onboarding/").url == result.url
    assert client.get("/owner/onboarding/device/").url == result.url
    page = client.get(result.url)
    assert page.context["form"]["code"].value() == "ONE"
    assert page.context["form"]["simple_mode"].value() is True
    result = client.post(result.url, branch_payload())
    assert result.url == "/owner/onboarding/device/"
    shop.refresh_from_db()
    assert shop.onboarding_completed_at
    with shop_context(shop):
        assert list(Service.objects.order_by("mode").values_list("mode", "price")) == [("kg", Decimal("35")), ("load", Decimal("150"))]
        assert PieceVariant.objects.get().price == Decimal("5")
        settings = Settings.objects.get()
        assert settings.min_kg == 3 and settings.kg_per_load == 7
        main = Branch.objects.get(name="Downtown")
    assert main.code == "ONE"
    assert main.simple_mode
    assert main.number == 1
    assert str(main.opening_time) == "08:00:00"
    assert str(main.closing_time) == "20:00:00"
    assert client.get(result.url).status_code == 200
    assert b"Downtown" in client.get(result.url).content
    invitation = client.post(result.url, {"setup_device": "yes"})
    assert invitation.url == f"/owner/?branch={main.pk}&setup=shared#add-device"
    page = client.get(invitation.url)
    assert page.context["selected_branch"] == main
    assert page.context["device_form"].initial["kind"] == "shared"
    assert client.post(result.url, {"setup_device": "later"}).url == "/owner/dashboard/"
    assert client.post("/owner/onboarding/", payload()).url == "/owner/dashboard/"
    assert Service.unscoped.filter(shop=shop).count() == 2


@pytest.mark.parametrize("change", [
    {"services-0-price": "-1"}, {"services-0-mode": "piece"},
    {"min_kg": "-1"}, {"kg_per_load": "0"}, {"kg_per_load": "-1"},
    {"services-0-DELETE": "on", "services-1-DELETE": "on"},
    {"services-1-name": "wash + dry + fold"},
])
def test_validation_does_not_partially_save(new_owner, change):
    client, shop = new_owner
    data = {**payload(), **change}
    assert client.post("/owner/onboarding/", data).status_code == 422
    shop.refresh_from_db()
    assert not shop.onboarding_completed_at
    assert not Service.unscoped.filter(shop=shop).exists()
    assert not PieceItem.unscoped.filter(shop=shop).exists()


def test_custom_rows_and_removing_defaults(new_owner):
    client, shop = new_owner
    data = {**payload(), "services-TOTAL_FORMS": "3", "services-0-DELETE": "on",
            "services-1-DELETE": "on", "services-2-name": "Wash only", "services-2-mode": "load",
            "services-2-price": "80", "pieces-0-DELETE": "on", "pieces-0-price": ""}
    assert client.post("/owner/onboarding/", data).status_code == 302
    assert Service.unscoped.get(shop=shop).name == "Wash only"
    assert not PieceItem.unscoped.filter(shop=shop).exists()


def test_forged_catalog_id_is_rejected(new_owner, setup_shop):
    client, shop = new_owner
    data = {**payload(), "services-0-record": str(setup_shop["service"].pk)}
    assert client.post("/owner/onboarding/", data).status_code == 422
    assert not Service.unscoped.filter(shop=shop).exists()



def branch_payload(**changes):
    return {"name": "Downtown", "code": "ONE", "opening_time": "08:00",
            "closing_time": "20:00", "simple_mode": "on", **changes}


def test_branch_cannot_skip_catalog_or_authentication(new_owner):
    client, shop = new_owner
    assert Client().get("/owner/onboarding/branch/").url == "/owner/login/"
    assert client.get("/owner/onboarding/branch/").url == "/owner/onboarding/"
    assert client.post("/owner/onboarding/branch/", branch_payload()).url == "/owner/onboarding/"
    assert not Branch.unscoped.filter(shop=shop).exists()
    client.post("/owner/onboarding/", payload())
    csrf = Client(enforce_csrf_checks=True)
    csrf.cookies["sessionid"] = client.cookies["sessionid"].value
    assert csrf.post("/owner/onboarding/branch/", branch_payload()).status_code == 403


@pytest.mark.parametrize("changes", [
    {"name": ""}, {"code": ""}, {"code": "X" * 31},
    {"opening_time": ""}, {"closing_time": ""}, {"opening_time": "25:00"},
    {"connection_mode": "hub"}, {"mode": "hub"},
])
def test_invalid_branch_retains_values_and_blocks_completion(new_owner, changes):
    client, shop = new_owner
    client.post("/owner/onboarding/", payload())
    response = client.post("/owner/onboarding/branch/", branch_payload(**changes))
    assert response.status_code == 422
    assert response.context["form"]["name"].value() == changes.get("name", "Downtown")
    shop.refresh_from_db()
    assert not shop.onboarding_completed_at
    assert not Branch.unscoped.filter(shop=shop).exists()
    assert client.get("/owner/onboarding/device/").url == "/owner/onboarding/branch/"


def test_branch_code_is_unique_case_insensitively_within_shop(new_owner):
    client, shop = new_owner
    with shop_context(shop):
        first = Branch.objects.create(shop=shop, number=1, name="Existing", code="FIRST")
        Branch.objects.create(shop=shop, number=2, name="Other branch", code="ONE")
    client.post("/owner/onboarding/", payload())
    response = client.post("/owner/onboarding/branch/", branch_payload(code="one"))
    assert response.status_code == 422
    assert "already exists in your shop" in response.context["form"].errors["code"][0]
    assert response.context["form"]["code"].value() == "one"
    first = Branch.unscoped.get(pk=first.pk)
    assert first.code == "FIRST"
    shop.refresh_from_db()
    assert not shop.onboarding_completed_at
    assert client.get("/owner/onboarding/device/").url == "/owner/onboarding/branch/"


def test_branch_code_can_be_reused_in_another_shop_and_overridden(new_owner):
    client, shop = new_owner
    other = Shop.objects.create(name="Other shop", code="OTHER")
    with shop_context(other):
        Branch.objects.create(shop=other, number=1, name="Other branch", code="CUSTOM")
    client.post("/owner/onboarding/", payload())
    data = branch_payload(code="CUSTOM", opening_time="22:00", closing_time="06:00")
    data.pop("simple_mode")
    response = client.post("/owner/onboarding/branch/", data)
    assert response.url == "/owner/onboarding/device/"
    branch = Branch.unscoped.get(shop=shop)
    assert branch.code == "CUSTOM"
    assert branch.mode == "direct"
    assert not branch.simple_mode
    assert str(branch.opening_time) == "22:00:00"
    assert str(branch.closing_time) == "06:00:00"
    assert client.post("/owner/onboarding/branch/", data).url == response.url
    assert Branch.unscoped.filter(shop=shop).count() == 1


def test_reopened_shop_reuses_first_branch_and_preserves_counters(new_owner):
    client, shop = new_owner
    with shop_context(shop):
        existing = Branch.objects.create(shop=shop, number=3, name="Existing", code="KEEP")
    client.post("/owner/onboarding/", payload())
    page = client.get("/owner/onboarding/branch/")
    assert page.context["form"]["code"].value() == "KEEP"
    client.post("/owner/onboarding/branch/", branch_payload(code="KEEP"))
    existing = Branch.unscoped.get(pk=existing.pk)
    assert existing.number == 3
    assert existing.job_seq == 3000
    assert Branch.unscoped.filter(shop=shop).count() == 1
