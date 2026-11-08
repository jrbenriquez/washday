"""Bounded, compare-and-set compensation; never rewrite historical records."""

from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from core.models import Branch
from core.operating_hours import require_job_operating_hours

from .journal import recorded_action
from .models import Action, Event
from .records import model

WINDOW = timedelta(seconds=6)
MUTABLE = {"jobs.job", "machines.load"}


def value(field, raw):
    return (
        field.target_field.to_python(raw) if field.is_relation else field.to_python(raw)
    )


def same(instance, snapshot):
    return all(
        f.attname in snapshot
        and getattr(instance, f.attname) == value(f, snapshot[f.attname])
        for f in instance._meta.concrete_fields
    )


def reversed_counts(branch):
    return [
        count_id
        for e in Event.objects.filter(branch=branch, type="action_undone")
        for count_id in e.payload.get("count_ids", [])
    ]


@recorded_action
@transaction.atomic
def compensate(branch, event_id, device, staff=None, now=None):
    from catalog.models import SupplyType
    from jobs.services import append_event
    from machines.models import Load
    from supplies.services import record

    branch = Branch.objects.select_for_update().get(pk=branch.pk)
    action = (
        Action.objects.select_for_update()
        .filter(branch=branch, event_id=event_id, device=device)
        .first()
    )
    now = now or timezone.now()
    if (
        not device
        or not action
        or action.undone_at
        or not timedelta(0) <= now - action.created_at <= WINDOW
    ):
        raise ValidationError("Undo is no longer available on this device.")
    latest = (
        Action.objects.filter(branch=branch, device=device)
        .order_by("-event__seq")
        .first()
    )
    if latest.pk != action.pk:
        raise ValidationError("Only your last reversible action can be undone.")
    if any(change["model"] == "jobs.job" for change in action.changes):
        require_job_operating_hours(branch)
    restores = []
    stocks = []
    count_ids = []
    for change in action.changes:
        label, before, after = change["model"], change["before"], change["after"]
        cls = model(label)
        if label in MUTABLE:
            obj = cls.objects.select_for_update().filter(pk=after["id"]).first()
            if not obj or not same(obj, after):
                raise ValidationError(
                    "This action has changed on another device and cannot be undone safely."
                )
            if label == "jobs.job" and before:
                from core.models import JobStage

                if not JobStage.objects.filter(
                    pk=before["status_id"], archived_at=None
                ).exists():
                    raise ValidationError("The original stage is no longer active.")
            if label == "machines.load":
                if (
                    before
                    and before["ended_at"] is None
                    and (
                        branch.simple_mode
                        or obj.machine.archived_at
                        or obj.machine.out_of_service
                        or obj.machine.category.archived_at
                    )
                ):
                    raise ValidationError(
                        "The original machine is no longer available to reopen this load."
                    )
                if (
                    Load.objects.filter(machine_id=obj.machine_id, ended_at=None)
                    .exclude(pk=obj.pk)
                    .exists()
                ):
                    raise ValidationError(
                        "The machine is already running a different load."
                    )
            restores.append((obj, before))
        elif label == "supplies.stockentry" and before is None:
            stocks.append(after)
        elif label == "supplies.stockcount" and before is None:
            count_ids.append(after["id"])
    if stocks:
        from catalog.supply_identity import identities

        ids = {
            str(key)
            for s in stocks
            for key in identities(SupplyType.objects.get(pk=s["supply_type_id"]))
        }
        if any(
            e.payload.get("supply_type") in ids
            for e in Event.objects.filter(
                branch=branch, type="stock_changed", seq__gt=action.event.seq
            )
        ):
            raise ValidationError(
                "Stock has changed since this action. Undo would no longer be safe."
            )
    # Close newly opened loads before reopening earlier ones (open-machine uniqueness).
    restores.sort(
        key=lambda pair: (
            pair[0]._meta.label_lower != "machines.load" or pair[1] is not None
        )
    )
    job_state = None
    number = None
    job_id = None
    for obj, before in restores:
        if before is None:
            if obj._meta.label_lower != "machines.load":
                raise ValidationError("This creation is not reversible.")
            obj.ended_at = now
            obj.ended_by = staff
            obj.cancelled_at = now
            obj.save(update_fields=["ended_at", "ended_by", "cancelled_at"])
        else:
            for f in obj._meta.concrete_fields:
                if f.name not in ("id", "shop"):
                    setattr(obj, f.attname, value(f, before[f.attname]))
            obj.save()
            if obj._meta.label_lower == "jobs.job":
                job_id = str(obj.id)
                number = obj.number
                job_state = {
                    "status": obj.status.name,
                    "paid_at": obj.paid_at.isoformat() if obj.paid_at else None,
                    "claimed_at": obj.claimed_at.isoformat()
                    if obj.claimed_at
                    else None,
                    "paid_amount": str(obj.paid_amount),
                    "method": obj.pay_method,
                    "reference": obj.pay_ref,
                }
    for entry in stocks:
        record(
            branch,
            SupplyType.objects.get(pk=entry["supply_type_id"]),
            -Decimal(entry["qty"]),
            "undo",
            staff,
            now,
            job=model("jobs.job").objects.filter(pk=entry["job_id"]).first()
            if entry["job_id"]
            else None,
            load=Load.objects.filter(pk=entry["load_id"]).first()
            if entry["load_id"]
            else None,
            reversal_of=entry["id"],
        )
    payments = list(
        Event.objects.filter(
            branch=branch,
            seq__gte=action.first_seq,
            seq__lte=action.event.seq,
            type__in=["payment_recorded", "self_service_started"],
        )
    )
    for payment in payments:
        append_event(
            branch,
            "payment_reversed",
            {
                "amount": payment.payload["amount"],
                "method": payment.payload["method"],
                "original_event": str(payment.id),
                "job_id": job_id,
                "number": number,
                "description": "Payment reversed by Undo",
                "undone_at": now.isoformat(),
            },
            payment.occurred_at,
            staff,
        )
    if action.kind == "claim":
        append_event(
            branch,
            "claim_reversed",
            {
                "job_id": job_id,
                "number": number,
                "description": "Release reversed by Undo",
            },
            action.event.occurred_at,
            staff,
        )
    action.undone_at = now
    action.save(update_fields=["undone_at"])
    return append_event(
        branch,
        "action_undone",
        {
            "action_event": str(action.event_id),
            "count_ids": count_ids,
            "job_id": job_id,
            "number": number,
            "job_state": job_state,
            "description": "Undone · " + action.kind.replace("_", " "),
        },
        now,
        staff,
    )
