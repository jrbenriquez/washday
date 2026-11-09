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
    assert result.url == "/owner/onboarding/device/"
    shop.refresh_from_db()
    assert shop.onboarding_completed_at
    with shop_context(shop):
        assert list(Service.objects.order_by("mode").values_list("mode", "price")) == [("kg", Decimal("35")), ("load", Decimal("150"))]
        assert PieceVariant.objects.get().price == Decimal("5")
        settings = Settings.objects.get()
        assert settings.min_kg == 3 and settings.kg_per_load == 7
        main = Branch.objects.get(name="Main Branch")
    assert client.get(result.url).status_code == 200
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
