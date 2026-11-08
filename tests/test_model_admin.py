from datetime import timedelta
from decimal import Decimal

import pytest
from django.apps import apps
from django.contrib import admin
from django.contrib.auth.models import Permission
from django.urls import reverse
from django.utils import timezone

from core.models import Branch, Shop
from core.tenancy import current_shop, shop_context
from jobs.services import create_job

APP_LABELS = (
    "core",
    "catalog",
    "customers",
    "jobs",
    "machines",
    "people",
    "supplies",
    "events",
)
APP_MODELS = [
    model for label in APP_LABELS for model in apps.get_app_config(label).get_models()
]
pytestmark = pytest.mark.django_db


def url(model, action="changelist", obj=None):
    return reverse(
        f"admin:{model._meta.app_label}_{model._meta.model_name}_{action}",
        args=[obj.pk] if obj else None,
    )


@pytest.fixture
def operator(client, django_user_model):
    user = django_user_model.objects.create_superuser(username="model-admin")
    client.force_login(user, backend="django.contrib.auth.backends.ModelBackend")
    return client


@pytest.mark.parametrize("model", APP_MODELS, ids=lambda model: model._meta.label)
def test_all_app_models_have_readonly_admin_entries(operator, model):
    assert admin.site.is_registered(model)
    response = operator.get(url(model))
    assert response.status_code == 200
    assert not response.context["has_add_permission"]
    assert not response.context["action_form"]
    assert operator.post(url(model, "add"), {}).status_code == 403


def test_all_populated_detail_views_render_without_tenant_context(operator, setup_shop):
    shop, branch = setup_shop["shop"], setup_shop["branch"]
    now = timezone.now()

    def add(app_label, model_name, **fields):
        return apps.get_model(app_label, model_name).objects.create(shop=shop, **fields)

    job = create_job(
        {
            "service": str(setup_shop["service"].pk),
            "kg": "3",
            "customer_name": "Admin customer",
        },
        branch,
        setup_shop["staff"],
    )[0]
    add("core", "ShopOwner", email="inspect@example.com")
    category = add("core", "MachineCategory", name="Washer", label_prefix="W")
    machine = add("core", "Machine", branch=branch, category=category, label="W1")
    device = add(
        "people",
        "Device",
        branch=branch,
        kind="shared",
        name="Counter",
        key_hash="device-secret-sentinel",
    )
    add(
        "people",
        "DeviceSetupCode",
        device=device,
        code_hash="code-secret-sentinel",
        expires_at=now + timedelta(minutes=10),
    )
    add(
        "people",
        "Shift",
        staff=setup_shop["staff"],
        device=device,
        started_at=now,
        ends_at=now + timedelta(hours=8),
    )
    supply = add("catalog", "SupplyType", name="Detergent", unit="cup")
    target = add("catalog", "SupplyType", name="Detergent replacement", unit="cup")
    add("catalog", "SupplyAlias", source=supply, target=target)
    add("catalog", "AddOnUse", addon=setup_shop["addon"], supply_type=supply, qty="0.5")
    add("machines", "Load", branch=branch, machine=machine, job=job, started_at=now)
    add(
        "supplies",
        "StockEntry",
        branch=branch,
        supply_type=supply,
        qty="10",
        reason="received",
        at=now,
    )
    count = add("supplies", "StockCount", branch=branch, at=now)
    add(
        "supplies",
        "StockCountLine",
        count=count,
        supply_type=supply,
        expected="10",
        counted="9",
        variance="-1",
    )
    add("supplies", "SupplyRequest", branch=branch, name="Detergent request")
    event = apps.get_model("events", "Event").objects.first()
    if not apps.get_model("events", "Action").objects.exists():
        add(
            "events",
            "Action",
            branch=branch,
            event=event,
            first_seq=event.seq,
            kind="test",
            changes={},
            created_at=now,
        )
    if not apps.get_model("events", "Outbox").objects.exists():
        add("events", "Outbox", event=event, frame={})
    add(
        "events",
        "HubCredential",
        branch=branch,
        key_hash="hub-secret-sentinel",
        epoch=1,
    )
    add("events", "Replica", branch=branch)
    add(
        "events",
        "Inbox",
        branch=branch,
        event_id=event.pk,
        seq=event.seq,
        frame={},
        digest="fixture-digest",
    )
    add("events", "ConfigurationAudit", branch=branch, kind="test", payload={}, at=now)
    # Every app table is represented, including immutable history and nullable FKs.
    for model in APP_MODELS:
        record = model.objects.first()
        assert record is not None, model._meta.label
        assert operator.get(url(model)).status_code == 200, model._meta.label
        response = operator.get(url(model, "change", record))
        assert response.status_code == 200, model._meta.label
        assert not response.context["has_change_permission"]
        assert not response.context["has_delete_permission"]
        for secret in (
            "device-secret-sentinel",
            "code-secret-sentinel",
            "hub-secret-sentinel",
        ):
            assert secret.encode() not in response.content
        assert current_shop() == shop.pk


def test_cross_shop_browsing_search_and_filter(operator, setup_shop):
    other = Shop.objects.create(code="OTHER", name="Other shop")
    with shop_context(other):
        foreign = Branch.objects.create(
            shop=other, name="Foreign branch", code="FOREIGN", number=1
        )
    path = url(Branch)
    response = operator.get(path)
    assert {b.pk for b in response.context["cl"].result_list} == {
        setup_shop["branch"].pk,
        foreign.pk,
    }
    response = operator.get(path, {"shop_id": str(other.pk)})
    assert [b.pk for b in response.context["cl"].result_list] == [foreign.pk]
    assert "OTHER" in response.content.decode()
    response = operator.get(path, {"q": "Foreign"})
    assert [b.pk for b in response.context["cl"].result_list] == [foreign.pk]
    assert operator.get(path, {"shop_id": "invalid"}).context["cl"].result_count == 0
    assert operator.get(url(Branch, "change", foreign)).status_code == 200


def test_staff_requires_model_view_permission(client, django_user_model, setup_shop):
    model = type(setup_shop["service"])
    user = django_user_model.objects.create_user(
        username="restricted-operator", is_staff=True
    )
    client.force_login(user, backend="django.contrib.auth.backends.ModelBackend")
    assert client.get(url(model)).status_code == 403
    assert client.get(url(model, "change", setup_shop["service"])).status_code == 403
    user.user_permissions.add(
        Permission.objects.get(
            content_type__app_label="catalog", codename="view_service"
        )
    )
    assert client.get(url(model)).status_code == 200
    assert client.get(url(model, "change", setup_shop["service"])).status_code == 200
    assert client.get(url(Branch)).status_code == 403


def test_admin_cannot_bypass_configuration_or_history_workflows(operator, setup_shop):
    service = setup_shop["service"]
    job = create_job(
        {"service": str(service.pk), "kg": "3"},
        setup_shop["branch"],
        setup_shop["staff"],
    )[0]
    event = apps.get_model("events", "Event").objects.first()
    for record in (service, setup_shop["branch"], job, event):
        model = type(record)
        assert (
            operator.post(
                url(model, "change", record), {"name": "Overwrite", "total": "0"}
            ).status_code
            == 403
        )
        assert (
            operator.post(url(model, "delete", record), {"post": "yes"}).status_code
            == 403
        )
        response = operator.post(
            url(model),
            {"action": "delete_selected", "_selected_action": str(record.pk)},
        )
        assert response.status_code == 200
        assert model.unscoped.filter(pk=record.pk).exists()
    assert type(service).unscoped.get(pk=service.pk).price == Decimal(service.price)


def test_nested_json_credentials_are_redacted_and_html_is_escaped(operator, setup_shop):
    model = apps.get_model("events", "Event")
    original = {
        "records": [
            {
                "fields": {
                    "pin_hash": "nested-pin-secret",
                    "key_hash": "nested-key-secret",
                    "code_hash": "nested-code-secret",
                    "name": "<script>alert(1)</script>",
                }
            }
        ]
    }
    event = model.objects.create(
        shop=setup_shop["shop"],
        branch=setup_shop["branch"],
        seq=1,
        type="test",
        payload=original,
        occurred_at=timezone.now(),
    )
    response = operator.get(url(model, "change", event))
    assert response.status_code == 200
    assert b"[redacted]" in response.content
    for secret in ("nested-pin-secret", "nested-key-secret", "nested-code-secret"):
        assert secret.encode() not in response.content
    assert b"<script>alert(1)</script>" not in response.content
    assert b"&lt;script&gt;alert(1)&lt;/script&gt;" in response.content
    assert model.objects.get(pk=event.pk).payload == original
