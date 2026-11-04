"""Aliases reconcile identity without rewriting immutable stock/count history."""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from core.models import Branch, Settings

from .models import AddOnUse, SupplyAlias, SupplyType


def resolve(supply):
    alias = SupplyAlias.objects.filter(source=supply).select_related("target").first()
    return alias.target if alias else supply


def identities(supply):
    target = resolve(supply)
    return [
        target.pk,
        *SupplyAlias.objects.filter(target=target).values_list("source_id", flat=True),
    ]


@transaction.atomic
def merge(source, target, settings_from="target"):
    list(Branch.objects.select_for_update().order_by("pk"))
    source = SupplyType.objects.select_for_update().get(pk=source.pk)
    target = SupplyType.objects.select_for_update().get(pk=target.pk)
    if (
        source.pk == target.pk
        or source.archived_at
        or target.archived_at
        or resolve(source).pk != source.pk
        or resolve(target).pk != target.pk
    ):
        raise ValidationError("Choose two distinct active, unmerged supply types.")
    if source.unit != target.unit:
        raise ValidationError(
            "Use the same unit on both supply types before merging; quantities are not converted."
        )
    source.archived_at = timezone.now()
    source.needs_merge = False
    source.save(update_fields=["archived_at", "needs_merge"])
    if settings_from == "source":
        for field in ("name", "unit", "low_level", "per_washer_load", "per_packed_job"):
            setattr(target, field, getattr(source, field))
    elif settings_from != "target":
        raise ValidationError("Choose which settings to keep.")
    target.needs_merge = False
    target.full_clean()
    target.save()
    SupplyAlias.objects.filter(target=source).update(target=target)
    SupplyAlias.objects.create(shop_id=source.shop_id, source=source, target=target)
    for use in AddOnUse.objects.filter(supply_type=source):
        existing = AddOnUse.objects.filter(addon=use.addon, supply_type=target).first()
        if existing:
            existing.qty += use.qty
            existing.save(update_fields=["qty"])
            use.delete()
        else:
            use.supply_type = target
            use.save(update_fields=["supply_type"])
    Settings.objects.filter(shop_id=source.shop_id).update(version=F("version") + 1)
    return target
