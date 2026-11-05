from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from catalog.models import SupplyType
from events.models import Action, Event
from events.undo import compensate
from jobs.history import project
from jobs.services import create_job
from jobs.transitions import advance, claim
from people.context import device_context
from people.models import Device
from supplies.models import StockCount, StockEntry
from supplies.services import balance, count_stock, receive


@pytest.fixture
def undo_setup(setup_shop):
    s = setup_shop
    device = Device.objects.create(
        shop=s["shop"], branch=s["branch"], name="Counter", kind="shared"
    )
    other = Device.objects.create(
        shop=s["shop"], branch=s["branch"], name="Other", kind="shared"
    )
    supply = SupplyType.objects.create(
        shop=s["shop"], name="Bag", unit="piece", per_packed_job=1
    )
    s["branch"].simple_mode = True
    s["branch"].save(update_fields=["simple_mode"])
    return {**s, "device": device, "other": other, "supply": supply}


def job(s):
    return create_job(
        {"service": str(s["service"].id), "kg": "3"}, s["branch"], s["staff"]
    )[0]


def action(s):
    return Action.objects.filter(device=s["device"]).order_by("-event__seq").first()


def test_undo_ready_restores_state_and_stock_without_erasing_history(undo_setup):
    s = undo_setup
    j = job(s)
    with device_context(s["device"]):
        advance(s["branch"], j.number, j.status_id, s["staff"])
        a = action(s)
        original = list(Event.objects.values_list("id", "payload"))
        entries = list(StockEntry.objects.values_list("id", "qty"))
        compensate(s["branch"], a.event_id, s["device"], s["staff"])
        j.refresh_from_db()
        assert (
            j.status.is_first
            and j.first_ready_at is None
            and balance(s["branch"], s["supply"]) == 0
        )
        assert all(Event.objects.filter(id=k, payload=v).exists() for k, v in original)
        assert all(StockEntry.objects.filter(id=k, qty=v).exists() for k, v in entries)
        advance(s["branch"], j.number, j.status_id, s["staff"])
        assert balance(s["branch"], s["supply"]) == -1


def test_window_device_last_action_and_repeated_compensation(undo_setup):
    s = undo_setup
    with device_context(s["device"]):
        receive(s["branch"], s["supply"].id, "10", s["staff"])
        a = action(s)
        for device, when in [
            (s["other"], a.created_at),
            (s["device"], a.created_at + timedelta(seconds=6, microseconds=1)),
        ]:
            with pytest.raises(ValidationError):
                compensate(s["branch"], a.event_id, device, now=when)
        compensate(
            s["branch"],
            a.event_id,
            s["device"],
            now=a.created_at + timedelta(seconds=6),
        )
        assert balance(s["branch"], s["supply"]) == 0
        with pytest.raises(ValidationError):
            compensate(s["branch"], a.event_id, s["device"])
        receive(s["branch"], s["supply"].id, "5", s["staff"])
        old = action(s)
        receive(s["branch"], s["supply"].id, "2", s["staff"])
        with pytest.raises(ValidationError):
            compensate(s["branch"], old.event_id, s["device"])


def test_undo_refuses_changed_job_and_never_partially_compensates(undo_setup):
    s = undo_setup
    j = job(s)
    with device_context(s["device"]):
        advance(s["branch"], j.number, j.status_id, s["staff"])
    a = action(s)
    j.refresh_from_db()
    with device_context(s["other"]):
        claim(s["branch"], j.number, j.status_id, {"pay_method": "cash"}, s["staff"])
    before = Event.objects.count()
    with device_context(s["device"]), pytest.raises(ValidationError):
        compensate(s["branch"], a.event_id, s["device"])
    assert Event.objects.count() == before and balance(s["branch"], s["supply"]) == -1


def test_claim_undo_corrects_ledger_history_and_owner_totals(undo_setup):
    from owner.workspace import collections

    s = undo_setup
    j = job(s)
    with device_context(s["device"]):
        advance(s["branch"], j.number, j.status_id, s["staff"])
        j.refresh_from_db()
        claim(s["branch"], j.number, j.status_id, {"pay_method": "cash"}, s["staff"])
        a = action(s)
        compensate(s["branch"], a.event_id, s["device"], s["staff"])
    j.refresh_from_db()
    assert not j.paid_at and not j.claimed_at
    assert collections([s["branch"]], timezone.localdate())["total"] == 0
    rows, _ = project(s["branch"])
    assert (
        rows[0]["status"] == "Ready"
        and not rows[0]["paid_at"]
        and not rows[0]["claimed_at"]
    )
    assert Event.objects.filter(type="payment_recorded").count() == 1
    assert Event.objects.filter(type="payment_reversed").count() == 1


def test_stock_count_undo_preserves_count_and_restores_balance(undo_setup):
    s = undo_setup
    with device_context(s["device"]):
        receive(s["branch"], s["supply"].id, "10", s["staff"])
        count_stock(s["branch"], {"count_" + str(s["supply"].id): "7"}, s["staff"])
        a = action(s)
        compensate(s["branch"], a.event_id, s["device"], s["staff"])
    assert StockCount.objects.count() == 1 and balance(s["branch"], s["supply"]) == 10


def test_used_today_is_net_of_deduction_undo(undo_setup):
    from types import SimpleNamespace

    from supplies.views import context

    s = undo_setup
    j = job(s)
    with device_context(s["device"]):
        advance(s["branch"], j.number, j.status_id, s["staff"])
        assert (
            context(SimpleNamespace(branch=s["branch"], GET={}))["stocks"][0]["used"]
            == 1
        )
        compensate(s["branch"], action(s).event_id, s["device"], s["staff"])
        assert (
            context(SimpleNamespace(branch=s["branch"], GET={}))["stocks"][0]["used"]
            == 0
        )


def test_nonreversible_success_does_not_offer_an_older_undo(undo_setup, client):
    from people.services import token_digest

    s = undo_setup
    s["device"].key_hash = token_digest("fixture-browser-token")
    s["device"].save(update_fields=["key_hash"])
    client.cookies["washday_device"] = "fixture-browser-token"
    r = client.post(
        "/supplies/receive/",
        {"supply_type": str(s["supply"].pk), "qty": "10"},
        follow=True,
    )
    assert b"data-undo-until" in r.content
    r = client.post(
        "/jobs/new/", {"service": str(s["service"].pk), "kg": "3"}, follow=True
    )
    assert r.status_code == 200 and b"data-undo-until" not in r.content
