from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from catalog.models import PieceItem, PieceVariant, Service
from core.models import Branch, Settings, Shop, ShopOwner
from core.tenancy import shop_context
from jobs.models import Job, JobLine
from jobs.services import create_job
from people.models import Device, Staff

pytestmark = pytest.mark.django_db


def reset(code, **options):
    output = StringIO()
    call_command("reset_shop_onboarding", shop_code=code, stdout=output, **options)
    return output.getvalue()


@pytest.mark.parametrize("name,code", [
    ("Test laundry", "TEST-001"),
    ("Laundry tEsT shop", "qa-TeSt-002"),
    ("TEST ONLY Laundry", "test"),
])
def test_reset_allowed_in_production(name, code, settings):
    settings.DEBUG = False
    shop = Shop.objects.create(name=name, code=code, onboarding_completed_at=timezone.now())
    assert "Onboarding reset" in reset(code)
    shop.refresh_from_db()
    assert shop.onboarding_completed_at is None


@pytest.mark.parametrize("name,code", [
    ("Real Laundry", "TEST-001"),
    ("Test Laundry", "LIVE-001"),
    ("Real Laundry", "LIVE-001"),
    ("", "TEST-001"),
    ("Test Laundry", ""),
])
def test_reset_requires_test_in_both_fields(name, code):
    completed = timezone.now()
    shop = Shop.objects.create(name=name, code=code, onboarding_completed_at=completed)
    with pytest.raises(CommandError, match="both the shop name and shop code"):
        reset(code)
    shop.refresh_from_db()
    assert shop.onboarding_completed_at == completed
    with pytest.raises(CommandError):
        reset(code, dry_run=True)


def test_missing_shop_or_inexact_code_cannot_reset_other_shops():
    completed = timezone.now()
    shop = Shop.objects.create(name="Test Laundry", code="TEST-001", onboarding_completed_at=completed)
    for code in ("MISSING-TEST", "TEST", "test-001"):
        with pytest.raises(CommandError, match="Shop not found"):
            reset(code)
    shop.refresh_from_db()
    assert shop.onboarding_completed_at == completed


def test_archived_shop_is_refused():
    completed = timezone.now()
    shop = Shop.objects.create(name="Test Laundry", code="TEST-001", onboarding_completed_at=completed, archived_at=completed)
    with pytest.raises(CommandError, match="archived"):
        reset(shop.code)
    shop.refresh_from_db()
    assert shop.onboarding_completed_at == completed


def test_dry_run_and_repeat_reset_are_safe():
    completed = timezone.now()
    shop = Shop.objects.create(name="Test Laundry", code="TEST-001", onboarding_completed_at=completed)
    assert "Dry run" in reset(shop.code, dry_run=True)
    shop.refresh_from_db()
    assert shop.onboarding_completed_at == completed
    reset(shop.code)
    assert "already pending" in reset(shop.code)
    assert "eligible" in reset(shop.code, dry_run=True)


def test_reset_preserves_data_and_reopens_owner_flow(setup_shop, client):
    s = setup_shop
    shop = s["shop"]
    user = get_user_model().objects.create_user(username="reset-owner")
    ShopOwner.objects.create(shop=shop, user=user, email="reset-owner@example.invalid")
    Device.objects.create(shop=shop, branch=s["branch"], name="Test counter", kind="shared")
    create_job({"service": str(s["service"].pk), "kg": "3"}, s["branch"], s["staff"])
    models = [Branch, Settings, Service, PieceItem, PieceVariant, Staff, Device, ShopOwner, Job, JobLine]
    before = {model: list(model.objects.order_by("pk").values()) for model in models}
    other = Shop.objects.create(name="Another Test shop", code="OTHER-TEST", onboarding_completed_at=timezone.now())
    other_completed = other.onboarding_completed_at
    client.force_login(user, backend="django.contrib.auth.backends.ModelBackend")
    assert client.get("/owner/dashboard/").status_code == 200
    assert "preserved" in reset(shop.code)
    shop.refresh_from_db()
    assert shop.onboarding_completed_at is None
    for model in models:
        assert list(model.objects.order_by("pk").values()) == before[model]
    other.refresh_from_db()
    assert other.onboarding_completed_at == other_completed
    response = client.get("/owner/dashboard/")
    assert response.url == "/owner/onboarding/"
    setup = client.get(response.url)
    assert setup.status_code == 200
    assert {form.initial["name"] for form in setup.context["services"]} == {s["service"].name, s["load"].name}
