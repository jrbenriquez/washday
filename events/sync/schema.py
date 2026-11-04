"""Validate every imported record and FK before bypassing model save hooks.

Raw imports preserve original timestamps and immutable IDs. Only this internal,
allow-listed boundary may import records; normal business writes use services.
"""

from django.core.exceptions import ValidationError

from core.models import TenantModel
from events.models import ImmutableModel
from events.records import model

DEVICE_UP = {
    "key_hash",
    "enrol_epoch",
    "key_revision",
    "last_seen_at",
    "pin_failures",
    "pin_locked_until",
    "setup_failures",
    "setup_locked_until",
}


def actor_belongs(staff, branch):
    from events.models import Event
    from jobs.models import Job

    return (
        staff.branch_id == branch.pk
        or Event.objects.filter(branch=branch, actor_staff=staff).exists()
        or Job.objects.filter(branch=branch, created_by=staff).exists()
    )


def decode(cls, data):
    expected = {f.attname for f in cls._meta.concrete_fields}
    if set(data) - expected or not {"id", "shop_id"}.issubset(data):
        raise ValidationError("Record fields do not match this protocol version.")
    result = {}
    for field in cls._meta.concrete_fields:
        if field.attname not in data:
            if field.name == "branch":
                raise ValidationError("Record branch is required.")
            if field.has_default():
                result[field.attname] = field.get_default()
                continue
            if field.null:
                result[field.attname] = None
                continue
            raise ValidationError("A required record field is missing.")
        raw = data[field.attname]
        result[field.attname] = (
            field.target_field.to_python(raw)
            if field.is_relation
            else field.to_python(raw)
        )
    return result


def related_branch(instance):
    label = instance._meta.label_lower
    if label == "people.devicesetupcode":
        return instance.device.branch_id
    if label == "people.shift":
        return instance.device.branch_id
    if label == "jobs.jobline":
        return instance.job.branch_id
    if label == "supplies.stockcountline":
        return instance.count.branch_id
    return getattr(instance, "branch_id", None)


def apply_record(record, branch, upward=True):
    from catalog.models import SupplyType
    from events.records import OPERATIONAL

    label = record["model"]
    if upward and label not in OPERATIONAL:
        raise ValidationError("Cloud-owned records cannot be pushed by a hub.")
    cls = model(label)
    data = decode(cls, record["fields"])
    if str(data["shop_id"]) != str(branch.shop_id):
        raise ValidationError("Record belongs to another shop.")
    obj = cls(**data)
    if related_branch(obj) not in (None, branch.pk):
        raise ValidationError("Record belongs to another branch.")
    # Reject same-shop cross-branch FK injection as well as cross-shop references.
    for field in cls._meta.concrete_fields:
        if not field.is_relation or field.name == "shop" or data[field.attname] is None:
            continue
        target = field.remote_field.model
        if issubclass(target, TenantModel):
            rel = target.objects.filter(pk=data[field.attname]).first()
            historical_actor = (
                rel is not None
                and target._meta.label_lower == "people.staff"
                and actor_belongs(rel, branch)
            )
            if rel is None or (
                related_branch(rel) not in (None, branch.pk) and not historical_actor
            ):
                raise ValidationError("Invalid record reference.")
    existing = cls.objects.filter(pk=obj.pk).first()
    if existing is not None and related_branch(existing) not in (None, branch.pk):
        raise ValidationError("Existing record belongs to another branch.")
    if existing is not None and isinstance(existing, ImmutableModel):
        if any(
            getattr(existing, field.attname) != data[field.attname]
            for field in cls._meta.concrete_fields
            if field.attname in record["fields"]
        ):
            raise ValidationError("An immutable record cannot be changed by replay.")
        return existing
    if upward and label == "catalog.supplytype":
        if existing:
            return existing  # Owner configuration wins over old offline frames.
        obj.needs_merge = SupplyType.objects.filter(
            name__iexact=obj.name, archived_at=None
        ).exists()
        from django.db.models import F

        from core.models import Settings

        Settings.objects.filter(shop_id=branch.shop_id).update(version=F("version") + 1)
    if existing is not None:
        # Older queued envelopes cannot clear fields introduced by a newer image.
        data = {key: val for key, val in data.items() if key in record["fields"]}
        if label == "people.device":
            local_enrolment_newer = (
                not upward
                and existing.config_revision == data.get("config_revision", 0)
                and existing.key_revision > data.get("key_revision", 0)
            )
            allowed = (
                DEVICE_UP
                if upward
                else set(data)
                - {
                    "id",
                    "shop_id",
                    "key_hash",
                    "enrol_epoch",
                    "key_revision",
                    "last_seen_at",
                    "pin_failures",
                    "pin_locked_until",
                    "setup_failures",
                    "setup_locked_until",
                }
            )
            if upward:
                if (
                    data.get("config_revision", 0) == existing.config_revision
                    and data.get("key_revision", 0) == existing.config_revision
                ):
                    allowed = allowed | {"revoked_at"}
                else:
                    allowed = allowed - {"key_hash", "key_revision", "enrol_epoch"}
            data = {k: v for k, v in data.items() if k in allowed}
            if local_enrolment_newer:
                data.pop("revoked_at", None)
        elif label == "people.devicesetupcode" and upward:
            data = {k: v for k, v in data.items() if k == "used_at"}
        elif (
            label == "people.devicesetupcode"
            and not upward
            and existing.used_at is not None
        ):
            # A delayed pull must not make a locally consumed setup code reusable.
            data.pop("used_at", None)
        cls.objects.filter(pk=obj.pk).update(
            **{k: v for k, v in data.items() if k != "id"}
        )
        return cls.objects.get(pk=obj.pk)
    if upward and label in ("people.device", "people.devicesetupcode"):
        raise ValidationError("Hub cannot provision new cloud devices.")
    obj.save_base(raw=True, force_insert=True)
    return obj
