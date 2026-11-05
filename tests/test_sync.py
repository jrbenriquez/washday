from copy import deepcopy
from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.db import transaction
from django.test import Client, override_settings
from django.utils import timezone

from catalog.models import SupplyType
from core.models import Branch, Settings, Shop
from core.tenancy import shop_context
from events.models import Event, HubCredential, Inbox, Outbox, Replica
from events.sync.catalog import bootstrap, configuration
from events.sync.client import tick
from events.sync.modes import activate_direct, activate_hub, prepare
from events.sync.server import push
from jobs.models import Job
from jobs.services import create_job
from supplies.models import StockEntry
from supplies.services import balance, count_stock, receive


@pytest.fixture
def hub(setup_shop):
    s = setup_shop
    token = prepare(s["branch"])
    credential = HubCredential.objects.get(branch=s["branch"])
    document = bootstrap(credential)
    activate_hub(s["branch"], document["acknowledged_seq"])
    s["branch"].refresh_from_db()
    credential.refresh_from_db()
    return {**s, "token": token, "credential": credential}


class RollbackCapture(Exception):
    pass


def frames(s, operation):
    result = []
    try:
        with (
            transaction.atomic(),
            override_settings(APP_ROLE="hub", HUB_BRANCH_ID=str(s["branch"].pk)),
        ):
            Replica.objects.create(
                shop=s["shop"],
                branch=s["branch"],
                writer_active=True,
                acknowledged_seq=s["branch"].event_seq,
            )
            operation()
            result = deepcopy(
                [
                    x.frame
                    for x in Outbox.objects.select_related("event").order_by(
                        "event__seq"
                    )
                ]
            )
            raise RollbackCapture()
    except RollbackCapture:
        pass
    return result


def create(s):
    return create_job(
        {
            "service": str(s["service"].pk),
            "kg": "3",
            "customer_name": "Offline customer",
            "pay_method": "cash",
        },
        s["branch"],
        s["staff"],
    )


def test_gap_duplicate_replay_and_dropped_ack_are_lossless(hub):
    s = hub
    batch = frames(s, lambda: create(s))
    assert len(batch) == 2
    response = push(s["credential"], [batch[1]])
    assert response["acknowledged_seq"] == 0 and Job.objects.count() == 0
    response = push(s["credential"], [batch[0]])
    assert response["acknowledged_seq"] == 2 and Job.objects.count() == 1
    original_ids = set(Event.objects.values_list("id", flat=True))
    assert push(s["credential"], batch)["acknowledged_seq"] == 2
    assert set(Event.objects.values_list("id", flat=True)) == original_ids
    assert (
        Job.objects.get().received_at.isoformat()
        == batch[0]["records"][1]["fields"]["received_at"]
    )


def test_conflicting_replay_and_foreign_scope_roll_back(hub):
    s = hub
    batch = frames(s, lambda: create(s))
    bad = deepcopy(batch)
    bad[1]["event"]["branch_id"] = "00000000-0000-0000-0000-000000000000"
    with pytest.raises(ValidationError):
        push(s["credential"], bad)
    assert not Job.objects.exists() and not Inbox.objects.exists()
    push(s["credential"], batch)
    bad = deepcopy(batch)
    bad[0]["job_seq"] += 1
    with pytest.raises(ValidationError):
        push(s["credential"], bad)
    assert Job.objects.count() == 1


def test_stock_records_and_immutable_counts_replicate_exactly(hub):
    s = hub
    supply = SupplyType.objects.create(shop=s["shop"], name="Detergent", unit="cup")

    def operate():
        receive(s["branch"], supply.pk, "10", s["staff"])
        count_stock(s["branch"], {"count_" + str(supply.pk): "8"}, s["staff"])

    batch = frames(s, operate)
    push(s["credential"], batch)
    assert balance(s["branch"], supply) == 8
    ids = list(StockEntry.objects.values_list("id", flat=True))
    push(s["credential"], batch)
    assert list(StockEntry.objects.values_list("id", flat=True)) == ids


def test_api_requires_hashed_branch_bound_hub_credentials(hub):
    s = hub
    c = Client()
    assert c.get("/sync/bootstrap/").status_code == 401
    assert (
        c.get("/sync/bootstrap/", HTTP_AUTHORIZATION="Bearer wrong").status_code == 401
    )
    r = c.get("/sync/pull/", HTTP_AUTHORIZATION="Bearer " + s["token"])
    assert r.status_code == 200 and r.json()["branch"]["id"] == str(s["branch"].pk)
    other = Shop.objects.create(name="Other", code="OTHER")
    with shop_context(other):
        Branch.objects.create(shop=other, name="Other branch", number=1, code="OTHER")
        Settings.objects.create(shop=other)
    payload = r.json()
    assert str(other.pk) not in str(payload)
    with override_settings(APP_ROLE="hub", HUB_BRANCH_ID=str(s["branch"].pk)):
        assert c.get("/owner/login/").status_code == 404
        assert (
            c.get("/sync/pull/", HTTP_AUTHORIZATION="Bearer " + s["token"]).status_code
            == 404
        )


def test_prepare_bootstrap_and_fenced_round_trip(hub):
    s = hub
    with pytest.raises(ValidationError):
        activate_direct(s["branch"], 0)
    batch = frames(s, lambda: create(s))
    push(s["credential"], batch)
    with pytest.raises(ValidationError):
        push(s["credential"], [], retire=True, last_seq=0)
    result = push(s["credential"], [], retire=True, last_seq=2)
    assert result["state"] == "frozen"
    activate_direct(s["branch"], 2)
    s["branch"].refresh_from_db()
    assert s["branch"].mode == "direct" and s["branch"].writer_epoch == 2
    with pytest.raises(ValidationError):
        push(s["credential"], batch)
    job, _ = create(s)
    assert job.number == 1002


def test_outbox_batches_and_acknowledgements_are_checked(hub):
    s = hub
    # Transport validates bounds before accepting an acknowledged cursor.
    calls = []

    def transport(path, data=None):
        calls.append((path, data))
        return {"acknowledged_seq": 999, "epoch": s["branch"].writer_epoch}

    with override_settings(APP_ROLE="hub", HUB_BRANCH_ID=str(s["branch"].pk)):
        Replica.objects.create(
            shop=s["shop"],
            branch=s["branch"],
            writer_active=True,
            pull_due=timezone.now() + timedelta(minutes=5),
        )
        create(s)
        with pytest.raises(ValidationError):
            tick(transport)
        replica = Replica.objects.get()
        assert replica.acknowledged_seq == 0 and replica.failures == 1
        assert not Outbox.objects.filter(sent_at__isnull=False).exists()
        previous = len(calls)
        tick(transport)
        assert len(calls) == previous


def test_cloud_direct_writes_need_no_outbox(setup_shop):
    create(setup_shop)
    assert not Outbox.objects.exists()


def test_offline_duplicate_supply_merge_keeps_both_histories(hub):
    from catalog.supply_identity import merge
    from supplies.models import StockEntry
    from supplies.services import add_type

    s = hub
    settings = Settings.objects.get()
    settings.staff_can_add_supply = True
    settings.save()
    batch = frames(
        s,
        lambda: add_type(
            s["branch"],
            {
                "name": "Sanitizer",
                "unit": "ml",
                "low_level": "1",
                "per_washer_load": "2",
                "per_packed_job": "0",
            },
            s["staff"],
        ),
    )
    survivor = SupplyType.objects.create(
        shop=s["shop"], name="sanitizer", unit="ml", per_washer_load=3
    )
    push(s["credential"], batch)
    duplicate = SupplyType.objects.get(needs_merge=True)
    StockEntry.objects.create(
        shop=s["shop"],
        branch=s["branch"],
        supply_type=survivor,
        qty=7,
        reason="received",
        at=timezone.now(),
    )
    StockEntry.objects.create(
        shop=s["shop"],
        branch=s["branch"],
        supply_type=duplicate,
        qty=3,
        reason="received",
        at=timezone.now(),
    )
    ids = set(Event.objects.values_list("id", flat=True))
    merge(duplicate, survivor, "target")
    assert balance(s["branch"], survivor) == 10
    assert (
        StockEntry.objects.count() == 2
        and set(Event.objects.values_list("id", flat=True)) == ids
    )
    push(s["credential"], batch)
    duplicate.refresh_from_db()
    assert duplicate.archived_at and balance(s["branch"], survivor) == 10


def test_cloud_owner_changes_do_not_consume_hub_sequence(hub):
    from events.models import ConfigurationAudit
    from people.services import save_staff

    s = hub
    before = Branch.objects.get(pk=s["branch"].pk).event_seq
    save_staff(s["branch"], "New hub staff", "1234")
    assert Branch.objects.get(pk=s["branch"].pk).event_seq == before
    assert ConfigurationAudit.objects.filter(branch=s["branch"]).exists()
    with pytest.raises(ValidationError):
        create(s)
    assert not Job.objects.exists()


def test_frozen_hub_refuses_new_business_writes(hub):
    s = hub
    with override_settings(APP_ROLE="hub", HUB_BRANCH_ID=str(s["branch"].pk)):
        Replica.objects.create(
            shop=s["shop"], branch=s["branch"], writer_active=False, frozen=True
        )
        with pytest.raises(ValidationError):
            create(s)
        assert not Job.objects.exists() and not Outbox.objects.exists()


def test_more_than_500_events_are_not_accepted_as_one_batch(hub):
    s = hub
    batch = frames(s, lambda: create(s))
    with pytest.raises(ValidationError):
        push(s["credential"], [batch[0]] * 501)
    assert not Inbox.objects.exists()


def test_historical_backlog_drains_in_bounded_batches(hub):
    from unittest.mock import patch

    s = hub
    supply = SupplyType.objects.create(
        shop=s["shop"], name="Backlog supply", unit="piece"
    )
    old = timezone.now() - timedelta(days=31)

    def operate():
        with patch("django.utils.timezone.now", return_value=old):
            for _ in range(510):
                receive(s["branch"], supply.pk, "1", s["staff"])

    batch = frames(s, operate)
    assert len(batch) == 510
    assert push(s["credential"], batch[:500])["acknowledged_seq"] == 500
    assert push(s["credential"], batch[500:])["acknowledged_seq"] == 510
    assert balance(s["branch"], supply) == 510 and Event.objects.count() == 510


def test_pull_failures_also_use_persisted_backoff(hub):
    s = hub
    calls = []

    def unavailable(path, data=None):
        calls.append(path)
        raise OSError("offline")

    with override_settings(APP_ROLE="hub", HUB_BRANCH_ID=str(s["branch"].pk)):
        Replica.objects.create(shop=s["shop"], branch=s["branch"], writer_active=True)
        with pytest.raises(OSError):
            tick(unavailable)
        tick(unavailable)
        assert len(calls) == 1


def test_consumed_setup_code_is_not_reopened_by_delayed_settings(hub):
    from events.records import row
    from events.sync.schema import apply_record
    from people.models import Device
    from people.services import issue_code

    s = hub
    d = Device.objects.create(
        shop=s["shop"], branch=s["branch"], kind="shared", name="Setup"
    )
    code, challenge = issue_code(d)
    delayed = row(challenge)
    challenge.used_at = timezone.now()
    challenge.save(update_fields=["used_at"])
    apply_record(delayed, s["branch"], upward=False)
    challenge.refresh_from_db()
    assert challenge.used_at is not None


def test_device_revisions_preserve_new_enrolment_and_apply_later_revoke(hub):
    from events.records import row
    from events.sync.schema import apply_record
    from people.models import Device

    s = hub
    d = Device.objects.create(
        shop=s["shop"],
        branch=s["branch"],
        name="Revisions",
        kind="shared",
        config_revision=3,
        key_revision=3,
        key_hash="a" * 64,
    )
    delayed = row(d)
    delayed["fields"].update(
        key_revision=2, key_hash="b" * 64, revoked_at=timezone.now().isoformat()
    )
    apply_record(delayed, s["branch"], upward=False)
    d.refresh_from_db()
    assert d.key_hash == "a" * 64 and d.revoked_at is None
    revoke = deepcopy(delayed)
    revoke["fields"]["config_revision"] = 4
    apply_record(revoke, s["branch"], upward=False)
    d.refresh_from_db()
    assert d.revoked_at
    stale = deepcopy(delayed)
    stale["fields"].update(key_revision=3, key_hash="c" * 64, revoked_at=None)
    apply_record(stale, s["branch"], upward=True)
    d.refresh_from_db()
    assert d.revoked_at and d.key_hash == "a" * 64
    new = deepcopy(stale)
    new["fields"].update(config_revision=4, key_revision=4)
    apply_record(new, s["branch"], upward=True)
    d.refresh_from_db()
    assert d.revoked_at is None and d.key_hash == "c" * 64


def test_bootstrap_retains_transferred_historical_actor_without_foreign_access(hub):
    from people.services import save_staff

    s = hub
    push(s["credential"], frames(s, lambda: create(s)))
    target = Branch.objects.create(
        shop=s["shop"], name="Other branch", code="OTHER", number=2
    )
    save_staff(target, s["staff"].name, "3456", staff=s["staff"])
    document = configuration(s["branch"])
    people = [r["fields"] for r in document["records"] if r["model"] == "people.staff"]
    historic = next(p for p in people if p["id"] == str(s["staff"].pk))
    assert historic["active"] is False and historic["pin_hash"] == "!"
    assert historic["branch_id"] == str(s["branch"].pk)
    assert all(p["branch_id"] == str(s["branch"].pk) for p in people)
    assert (
        Event.objects.filter(branch=s["branch"]).first().actor_staff_id == s["staff"].pk
    )


def test_older_device_envelope_keeps_new_schema_defaults(hub):
    from events.records import row
    from events.sync.schema import apply_record
    from people.models import Device

    s = hub
    d = Device.objects.create(
        shop=s["shop"], branch=s["branch"], name="Previous image", kind="shared"
    )
    old = row(d)
    old["fields"].pop("config_revision")
    old["fields"].pop("key_revision")
    apply_record(old, s["branch"], upward=True)
    d.refresh_from_db()
    assert d.config_revision == 0 and d.key_revision == 0


def test_merge_reconciles_addon_recipes_without_changing_ledgers(hub):
    from decimal import Decimal

    from catalog.models import AddOnUse
    from catalog.supply_identity import merge

    s = hub
    source = SupplyType.objects.create(
        shop=s["shop"], name="Soap duplicate", unit="cup"
    )
    target = SupplyType.objects.create(shop=s["shop"], name="Soap survivor", unit="cup")
    AddOnUse.objects.create(
        shop=s["shop"], addon=s["addon"], supply_type=source, qty="1.5"
    )
    AddOnUse.objects.create(
        shop=s["shop"], addon=s["addon"], supply_type=target, qty="2.0"
    )
    merge(source, target)
    assert AddOnUse.objects.filter(addon=s["addon"]).count() == 1
    assert AddOnUse.objects.get(addon=s["addon"]).qty == Decimal("3.5")


def test_active_key_cannot_bootstrap_another_writer(hub):
    with pytest.raises(ValidationError):
        bootstrap(hub["credential"])


def test_http_push_validates_and_applies_the_wire_envelope(hub):
    s = hub
    batch = frames(s, lambda: create(s))
    client = Client()
    response = client.post(
        "/sync/push/",
        {"events": batch},
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer " + s["token"],
    )
    assert response.status_code == 200, response.json()
    assert response.json()["acknowledged_seq"] == 2 and Job.objects.count() == 1
    response = client.post(
        "/sync/push/",
        {
            "events": [
                {"protocol": 1, "epoch": 1, "job_seq": 1, "event": {}, "records": [1]}
            ]
        },
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer " + s["token"],
    )
    assert response.status_code == 400
