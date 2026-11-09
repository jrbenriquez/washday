from decimal import Decimal
from io import StringIO
from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.urls import reverse
from django.utils import timezone

from catalog.models import Service, SupplyType
from core.models import (
    Branch,
    JobStage,
    Machine,
    MachineCategory,
    Settings,
    Shop,
    ShopOwner,
)
from core.tenancy import current_shop, shop_context
from owner.adapters import approved_owner
from people.models import Staff

pytestmark = pytest.mark.django_db


def create_shop(**overrides):
    options = {
        "shop_code": "NEW-SHOP",
        "name": "New Laundry",
        "min_kg": "3",
        "kg_per_load": "7",
        "interactive": False,
        "stdout": StringIO(),
    }
    options.update(overrides)
    call_command("create_shop", **options)
    return options["stdout"].getvalue()


def test_provisions_production_settings_and_workflow_without_fixtures(settings):
    settings.DEBUG = False
    output = create_shop(owner_email="  Owner@Example.com  ")
    shop = Shop.objects.get(code="NEW-SHOP")
    assert shop.name == "New Laundry" and shop.timezone == "Asia/Manila"
    with shop_context(shop):
        config = Settings.objects.get()
        assert (config.min_kg, config.kg_per_load) == (Decimal(3), Decimal(7))
        assert config.pin_enabled and config.pin_actions == [
            "payment",
            "claim",
            "override",
        ]
        stages = list(JobStage.objects.order_by("sort_order"))
        assert [s.name for s in stages] == [
            "Received",
            "Washing",
            "Drying",
            "Folding",
            "Ready",
        ]
        assert [s.sort_order for s in stages] == list(range(5))
        assert [s.name for s in stages if s.is_first] == ["Received"]
        assert [s.name for s in stages if s.is_last] == ["Ready"]
        assert stages[1].machine_category.name == "Washer"
        assert stages[1].machine_category.uses_wash_supplies
        assert stages[2].machine_category.name == "Dryer"
        assert stages[1].ask_for_machine and stages[2].ask_for_machine
        assert stages[2].move_on_when_unloaded
        assert MachineCategory.objects.count() == 2
        assert all(
            not m.objects.exists()
            for m in (Branch, Machine, Service, SupplyType, Staff)
        )
        owner = ShopOwner.objects.get()
        assert (
            owner.email == "owner@example.com"
            and owner.active
            and owner.user_id is None
        )
    assert current_shop() is None
    assert "Created shop NEW-SHOP" in output and "/owner/login/" in output
    # The provisioned record is eligible for the existing verified Google flow.
    login = SimpleNamespace(
        account=SimpleNamespace(provider="google"),
        email_addresses=[SimpleNamespace(email="OWNER@example.com", verified=True)],
    )
    assert approved_owner(login).pk == owner.pk
    login.email_addresses[0].verified = False
    assert approved_owner(login) is None


def test_interactive_owner_prompt(monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    prompts = []

    def answer(prompt):
        prompts.append(prompt)
        return "  Prompt@Example.com  "

    monkeypatch.setattr("builtins.input", answer)
    create_shop(interactive=True)
    assert len(prompts) == 1 and "Google email" in prompts[0]
    assert ShopOwner.unscoped.get().email == "prompt@example.com"


def test_bare_command_prompts_for_all_details(monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    answers = iter(["GUIDED", "Guided Laundry", "0", "8.5", "", "Owner@Example.com"])
    prompts = []

    def answer(prompt):
        prompts.append(prompt)
        return next(answers)

    monkeypatch.setattr("builtins.input", answer)
    call_command("create_shop", stdout=StringIO())
    shop = Shop.objects.get(code="GUIDED")
    assert shop.name == "Guided Laundry" and shop.timezone == "Asia/Manila"
    config = Settings.unscoped.get(shop=shop)
    assert (config.min_kg, config.kg_per_load) == (Decimal(0), Decimal("8.5"))
    assert ShopOwner.unscoped.get(shop=shop).email == "owner@example.com"
    assert len(prompts) == 6 and "Google email" in prompts[-1]


def test_partial_flags_prompt_only_for_missing_details(monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    prompts = []

    def answer(prompt):
        prompts.append(prompt)
        return "Guided Laundry"

    monkeypatch.setattr("builtins.input", answer)
    create_shop(
        name=None, interactive=True, timezone="UTC", owner_email="flag@example.com"
    )
    assert prompts == ["Shop name: "]
    assert Shop.objects.get().timezone == "UTC"
    assert ShopOwner.unscoped.get().email == "flag@example.com"


def test_required_prompts_retry_blank_values(monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    answers = iter(["", "  ", "Guided Laundry"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    errors = StringIO()
    create_shop(
        name=None, interactive=True, timezone="UTC", owner_email="", stderr=errors
    )
    assert errors.getvalue().count("This value is required.") == 2
    assert Shop.objects.get().name == "Guided Laundry"
    assert not ShopOwner.unscoped.exists()


@pytest.mark.parametrize("terminal,interactive", [(True, False), (False, True)])
def test_missing_details_without_prompts_fail_clearly(
    monkeypatch, terminal, interactive
):
    monkeypatch.setattr("sys.stdin.isatty", lambda: terminal)
    monkeypatch.setattr("builtins.input", lambda _: pytest.fail("Unexpected prompt"))
    with pytest.raises(
        CommandError,
        match="Missing required options: --shop-code, --name, --min-kg, --kg-per-load",
    ):
        call_command("create_shop", interactive=interactive, stdout=StringIO())
    assert not Shop.objects.exists()


@pytest.mark.parametrize("error", [EOFError, KeyboardInterrupt])
def test_cancelled_shop_details_save_nothing(monkeypatch, error):
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)

    def cancel(_):
        raise error()

    monkeypatch.setattr("builtins.input", cancel)
    with pytest.raises(CommandError, match="cancelled"):
        call_command("create_shop", stdout=StringIO())
    assert not Shop.objects.exists()


@pytest.mark.parametrize("email", [None, "", "flag@example.com"])
def test_noinput_never_prompts(monkeypatch, email):
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _: pytest.fail("Unexpected prompt"))
    create_shop(owner_email=email)
    assert ShopOwner.unscoped.count() == bool(email)


def test_nonterminal_never_prompts(monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    monkeypatch.setattr("builtins.input", lambda _: pytest.fail("Unexpected prompt"))
    output = create_shop(interactive=True)
    assert "No owner email approved" in output
    assert not ShopOwner.unscoped.exists()


def test_blank_interactive_email_skips_owner(monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _: "  ")
    create_shop(interactive=True)
    assert Shop.objects.count() == 1 and not ShopOwner.unscoped.exists()


@pytest.mark.parametrize("error", [EOFError, KeyboardInterrupt])
def test_cancelled_prompt_saves_nothing(monkeypatch, error):
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)

    def cancel(_):
        raise error()

    monkeypatch.setattr("builtins.input", cancel)
    with pytest.raises(CommandError, match="cancelled"):
        create_shop(interactive=True)
    assert not Shop.objects.exists()


@pytest.mark.parametrize(
    "options",
    [
        {"name": " "},
        {"name": "x" * 161},
        {"shop_code": " "},
        {"shop_code": "x" * 41},
        {"timezone": "Unknown/Zone"},
        {"timezone": "/etc/passwd"},
        {"min_kg": "-1"},
        {"kg_per_load": "0"},
        {"kg_per_load": "-2"},
        {"min_kg": "nan"},
        {"kg_per_load": "Infinity"},
        {"min_kg": "abc"},
        {"kg_per_load": "1.23"},
        {"min_kg": "100000"},
        {"owner_email": "invalid-email"},
    ],
)
def test_invalid_inputs_leave_no_partial_shop(options):
    with pytest.raises(CommandError):
        create_shop(**options)
    assert not Shop.objects.exists()
    assert all(
        not model.unscoped.exists()
        for model in (Settings, JobStage, MachineCategory, ShopOwner)
    )
    assert current_shop() is None


@pytest.mark.parametrize("archived", [False, True])
def test_duplicate_shop_refused_without_overwriting(archived):
    create_shop()
    shop = Shop.objects.get()
    if archived:
        shop.archived_at = timezone.now()
        shop.save()
    with pytest.raises(CommandError):
        create_shop(name="Replacement", owner_email="new@example.com")
    shop.refresh_from_db()
    assert shop.name == "New Laundry" and Shop.objects.count() == 1
    assert Settings.unscoped.count() == 1 and JobStage.unscoped.count() == 5
    assert not ShopOwner.unscoped.exists()


def test_cross_shop_owner_email_rolls_back_all_new_records():
    create_shop(shop_code="FIRST", owner_email="owner@example.com")
    original = ShopOwner.unscoped.get()
    with pytest.raises(CommandError, match="another shop"):
        create_shop(owner_email="OWNER@example.com")
    assert list(Shop.objects.values_list("code", flat=True)) == ["FIRST"]
    assert Settings.unscoped.count() == 1 and JobStage.unscoped.count() == 5
    assert (
        MachineCategory.unscoped.count() == 2
        and ShopOwner.unscoped.get().pk == original.pk
    )


def test_new_owner_can_open_workspace_and_add_first_branch(client):
    create_shop(owner_email="owner@example.com", timezone="UTC", min_kg="0")
    owner = ShopOwner.unscoped.get()
    user = get_user_model().objects.create_user(username="new-owner", email=owner.email)
    with shop_context(owner.shop):
        owner.user = user
        owner.save(update_fields=["user"])
    client.force_login(user, backend="django.contrib.auth.backends.ModelBackend")
    assert client.get("/owner/dashboard/").url == reverse("owner_onboarding")
    # Exercise branch management independently after first-owner setup.
    owner.shop.onboarding_completed_at = timezone.now()
    owner.shop.save(update_fields=["onboarding_completed_at"])
    for path in [
        "/owner/dashboard/",
        "/owner/settings/",
        "/owner/machines/",
        reverse("owner_branch_manage"),
    ]:
        assert client.get(path).status_code == 200
    response = client.post(
        reverse("owner_branch_new"),
        {
            "name": "First branch",
            "code": "BRANCH-ONE",
            "opening_time": "08:00",
            "closing_time": "18:00",
            "simple_mode": "on",
        },
    )
    assert response.status_code == 302
    branch = Branch.unscoped.get()
    assert (
        branch.shop_id == owner.shop_id
        and branch.number == 1
        and branch.job_seq == 1000
    )
    assert owner.shop.timezone == "UTC"


def test_allow_owner_still_reactivates_existing_owner():
    create_shop(owner_email="owner@example.com")
    owner = ShopOwner.unscoped.get()
    with shop_context(owner.shop):
        owner.active = False
        owner.save(update_fields=["active"])
    call_command(
        "allow_owner", "OWNER@example.com", shop_code="NEW-SHOP", stdout=StringIO()
    )
    owner = ShopOwner.unscoped.get(pk=owner.pk)
    assert owner.active and ShopOwner.unscoped.count() == 1
