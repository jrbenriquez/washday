from events.journal import recorded_action
from people.context import current_device
from collections import defaultdict
from decimal import Decimal
from django.db import transaction
from django.db.models import Sum
from django.http import Http404
from django.core.exceptions import ValidationError, PermissionDenied
from django.utils import timezone
from core.models import Branch, Settings
from catalog.models import SupplyType, AddOnUse
from catalog.supply_identity import resolve, identities
from jobs.services import dec, get_active, append_event
from .models import StockEntry, StockCount, StockCountLine, SupplyRequest


def qty(raw):
    value = dec(raw)
    if value < 0 or value > Decimal("999999999.999") or value.as_tuple().exponent < -3:
        raise ValidationError(
            "Enter a nonnegative quantity with at most three decimal places."
        )
    return value


def balance(branch, supply):
    return StockEntry.objects.filter(
        branch=branch, supply_type_id__in=identities(supply)
    ).aggregate(total=Sum("qty"))["total"] or Decimal("0")


def record(
    branch, supply, amount, reason, staff, at, job=None, load=None, reversal_of=None
):
    supply = resolve(supply)
    if not amount:
        return None
    if (
        reason == "packed_job"
        and StockEntry.objects.filter(
            job=job, supply_type=supply, reason=reason
        ).exists()
    ):
        reason = "packed_job_reapplied"
    entry = StockEntry.objects.create(
        shop_id=branch.shop_id,
        branch=branch,
        supply_type=supply,
        qty=amount,
        reason=reason,
        by=staff,
        at=at,
        job=job,
        load=load,
        reverses_id=reversal_of,
    )
    payload = {
        "reverses": str(reversal_of) if reversal_of else None,
        "stock_entry": str(entry.id),
        "supply_type": str(supply.id),
        "supply": supply.name,
        "qty": str(amount),
        "reason": reason,
        "description": f"{supply.name} · {amount:+f} {supply.unit} · {reason.replace('_', ' ')}",
    }
    if job:
        payload.update(job_id=str(job.id), number=job.number)
    if load:
        payload["load_id"] = str(load.id)
    append_event(branch, "stock_changed", payload, at, staff)
    return entry


def deduct_addons(branch, job, addon_ids, staff, at):
    amounts = defaultdict(lambda: Decimal("0"))
    types = {}
    for use in AddOnUse.objects.filter(
        addon_id__in=addon_ids, supply_type__archived_at=None
    ).select_related("supply_type"):
        if use.qty < 0:
            raise ValidationError("Recipe quantities must not be negative.")
        amounts[use.supply_type_id] += use.qty
        types[use.supply_type_id] = use.supply_type
    for key, amount in amounts.items():
        record(branch, types[key], -amount, "addon", staff, at, job=job)


def deduct_load(branch, load, staff, at):
    if not load.machine.category.uses_wash_supplies:
        return
    for supply in SupplyType.objects.filter(archived_at=None, per_washer_load__gt=0):
        record(
            branch,
            supply,
            -supply.per_washer_load,
            "washer_load",
            staff,
            at,
            job=load.job,
            load=load,
        )


def deduct_packing(branch, job, staff, at):
    for supply in SupplyType.objects.filter(archived_at=None, per_packed_job__gt=0):
        record(branch, supply, -supply.per_packed_job, "packed_job", staff, at, job=job)


@transaction.atomic
@recorded_action
def receive(branch, supply_id, raw, staff=None):
    branch = Branch.objects.select_for_update().get(pk=branch.pk)
    supply = get_active(SupplyType, supply_id, archived_at=None)
    amount = qty(raw)
    if amount <= 0:
        raise ValidationError("Receive a positive amount.")
    return record(branch, supply, amount, "received", staff, timezone.now())


@transaction.atomic
@recorded_action
def count_stock(branch, data, staff=None):
    branch = Branch.objects.select_for_update().get(pk=branch.pk)
    partial = str(data.get("partial", "")) == "1"
    active = list(SupplyType.objects.filter(archived_at=None))
    types = {str(s.id): s for s in active}
    entered = {}
    for key, value in data.items():
        if key.startswith("count_"):
            sid = key[6:]
            if sid not in types:
                raise Http404()
            if value.strip():
                entered[sid] = qty(value)
    if not entered:
        raise ValidationError("Enter at least one counted quantity.")
    if not partial and set(entered) != set(types):
        raise ValidationError(
            "A full count needs every active supply. Use Partial count for a spot check."
        )
    at = timezone.now()
    count = StockCount.objects.create(
        shop_id=branch.shop_id,
        branch=branch,
        by=staff,
        at=at,
        partial=partial,
        device=current_device(),
    )
    lines = []
    for sid, amount in entered.items():
        supply = types[sid]
        expected = balance(branch, supply)
        variance = amount - expected
        StockCountLine.objects.create(
            shop_id=branch.shop_id,
            count=count,
            supply_type=supply,
            expected=expected,
            counted=amount,
            variance=variance,
        )
        record(branch, supply, variance, "count_adjust", staff, at)
        lines.append(
            {
                "supply": supply.name,
                "supply_type": sid,
                "expected": str(expected),
                "counted": str(amount),
                "variance": str(variance),
            }
        )
    append_event(
        branch,
        "stock_counted",
        {
            "count_id": str(count.id),
            "partial": partial,
            "lines": lines,
            "description": ("Partial" if partial else "Full") + " stock count saved",
        },
        at,
        staff,
    )
    return count


@transaction.atomic
@recorded_action
def request_supply(branch, name, note="", staff=None):
    branch = Branch.objects.select_for_update().get(pk=branch.pk)
    name = name.strip()
    if not name or len(name) > 120:
        raise ValidationError("Enter a supply name up to 120 characters.")
    r = SupplyRequest.objects.create(
        shop_id=branch.shop_id, branch=branch, name=name, note=note, requested_by=staff
    )
    append_event(
        branch,
        "supply_requested",
        {
            "request_id": str(r.id),
            "name": name,
            "description": f"New supply requested · {name}",
        },
        r.created_at,
        staff,
    )
    return r


@transaction.atomic
@recorded_action
def add_type(branch, data, staff=None):
    branch = Branch.objects.select_for_update().get(pk=branch.pk)
    if (
        not Settings.objects.select_for_update()
        .get(shop_id=branch.shop_id)
        .staff_can_add_supply
    ):
        raise PermissionDenied("Ask the owner to add a supply or unlock staff adding.")
    name = data.get("name", "").strip()
    unit = data.get("unit", "").strip()
    if not name or len(name) > 120 or not unit or len(unit) > 30:
        raise ValidationError("Enter a supply name and unit.")
    existing = SupplyType.objects.filter(name__iexact=name).first()
    if existing:
        raise ValidationError(
            "This supply name already exists."
            if not existing.archived_at
            else "This archived supply must be restored by the owner."
        )
    s = SupplyType.objects.create(
        shop_id=branch.shop_id,
        name=name,
        unit=unit,
        low_level=qty(data.get("low_level", "")),
        per_washer_load=qty(data.get("per_washer_load", "")),
        per_packed_job=qty(data.get("per_packed_job", "")),
    )
    append_event(
        branch,
        "supply_type_added",
        {"supply_type": str(s.id), "description": f"Supply type added · {s.name}"},
        timezone.now(),
        staff,
    )
    return s
