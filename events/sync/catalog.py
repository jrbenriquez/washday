from django.core.exceptions import ValidationError
from django.db import transaction

from core.models import Branch, Settings, Shop
from events.models import Event, HubCredential, Replica
from events.records import CATALOG, fields, model, row

from .schema import apply_record, decode


def queryset(label, branch):
    cls = model(label)
    if label in ("core.machine", "people.staff", "people.device"):
        return cls.objects.filter(branch=branch)
    if label == "people.devicesetupcode":
        from django.db.models import F

        return cls.objects.filter(device__branch=branch).order_by(
            F("used_at").desc(nulls_last=True), "expires_at", "id"
        )
    return cls.objects.all()


@transaction.atomic
def configuration(branch):
    branch = Branch.objects.select_for_update().select_related("shop").get(pk=branch.pk)
    Settings.objects.select_for_update().get(shop_id=branch.shop_id)
    from jobs.models import Job
    from machines.models import Load
    from people.models import Shift, Staff
    from supplies.models import StockCount, StockEntry

    from .assets import export_logo

    referenced = set(
        Event.objects.filter(branch=branch).values_list("actor_staff_id", flat=True)
    )
    for cls, relation, names in [
        (Job, "branch", ["created_by_id"]),
        (Load, "branch", ["started_by_id", "ended_by_id"]),
        (StockEntry, "branch", ["by_id"]),
        (StockCount, "branch", ["by_id"]),
        (Shift, "device__branch", ["staff_id"]),
    ]:
        for name in names:
            referenced.update(
                cls.objects.filter(**{relation: branch}).values_list(name, flat=True)
            )
    historical = []
    for person in Staff.objects.filter(pk__in=referenced).exclude(branch=branch):
        record = row(person)
        record["fields"].update(branch_id=str(branch.pk), active=False, pin_hash="!")
        historical.append(record)
    return {
        "protocol": 1,
        "shop": fields(branch.shop),
        "branch": fields(branch),
        "logo_asset": export_logo(branch.shop),
        "version": Settings.objects.get(shop_id=branch.shop_id).version,
        "records": [row(obj) for label in CATALOG for obj in queryset(label, branch)]
        + historical,
    }


@transaction.atomic
def bootstrap(credential):
    from customers.models import Customer
    from jobs.models import Job
    from machines.models import Load
    from people.models import Shift
    from supplies.models import StockCount, StockCountLine, StockEntry, SupplyRequest

    branch = (
        Branch.objects.select_for_update()
        .select_related("shop")
        .get(pk=credential.branch_id)
    )
    credential = HubCredential.objects.select_for_update().get(pk=credential.pk)
    if credential.state != "prepared" or branch.mode != "direct":
        raise ValidationError(
            "Bootstrap requires a prepared key and the direct writer. Fence an existing hub before restoring a second database."
        )
    customer_ids = Job.objects.filter(branch=branch).values_list(
        "customer_id", flat=True
    )
    sets = [
        Customer.objects.filter(pk__in=customer_ids),
        Shift.objects.filter(device__branch=branch),
        Job.objects.filter(branch=branch),
        model("jobs.jobline").objects.filter(job__branch=branch),
        Load.objects.filter(branch=branch),
        StockCount.objects.filter(branch=branch),
        StockCountLine.objects.filter(count__branch=branch),
        StockEntry.objects.filter(branch=branch),
        SupplyRequest.objects.filter(branch=branch),
    ]
    result = configuration(branch)
    result["operations"] = [row(obj) for qs in sets for obj in qs]
    result["events"] = [
        fields(e) for e in Event.objects.filter(branch=branch).order_by("seq")
    ]
    credential.bootstrap_seq = branch.event_seq
    credential.save(update_fields=["bootstrap_seq"])
    result["active"] = credential.state == "active" and branch.mode == "hub"
    result["acknowledged_seq"] = branch.event_seq
    return result


@transaction.atomic
def apply_configuration(document, initial=False):
    from django.conf import settings

    from core.tenancy import shop_context

    if document.get("protocol") != 1 or str(document["branch"]["id"]) != str(
        settings.HUB_BRANCH_ID
    ):
        raise ValidationError(
            "Bootstrap/configuration has the wrong branch or protocol."
        )
    shop_data = document["shop"]
    branch_data = document["branch"]
    if not initial:
        with shop_context(shop_data["id"]):
            current = (
                Branch.objects.select_for_update().filter(pk=branch_data["id"]).first()
            )
            if current is None:
                raise ValidationError("Configuration does not match this hub's shop.")
            config = Settings.objects.select_for_update().get(shop_id=current.shop_id)
            if (
                document["version"] < config.version
                or branch_data["writer_epoch"] < current.writer_epoch
            ):
                return current
    from .assets import import_logo

    import_logo(document)
    if str(branch_data["shop_id"]) != str(shop_data["id"]):
        raise ValidationError("Invalid shop binding.")
    if (
        Branch.unscoped.exclude(pk=branch_data["id"]).exists()
        or Shop.objects.exclude(pk=shop_data["id"]).exists()
    ):
        raise ValidationError(
            "A hub database may contain only its assigned branch and shop."
        )
    shop = Shop(
        **{
            f.attname: (
                f.target_field.to_python(shop_data[f.attname])
                if f.is_relation
                else f.to_python(shop_data[f.attname])
            )
            for f in Shop._meta.concrete_fields
        }
    )
    if initial:
        if Shop.objects.exists():
            raise ValidationError("Bootstrap needs an empty, migrated hub database.")
        shop.save_base(raw=True, force_insert=True)
    else:
        Shop.objects.filter(pk=shop.pk).update(
            **{k: v for k, v in fields(shop).items() if k != "id"}
        )
    with shop_context(shop):
        b = Branch(**decode(Branch, branch_data))
        if initial:
            b.save_base(raw=True, force_insert=True)
            replica = Replica.objects.create(
                shop=shop, branch=b, acknowledged_seq=document["acknowledged_seq"]
            )
        else:
            b = Branch.objects.select_for_update().get(pk=b.pk)
            replica = Replica.objects.select_for_update().get(branch=b)
            # Never overwrite local job/event counters with an older cloud view.
            for key in (
                "name",
                "code",
                "mode",
                "hub_url",
                "simple_mode",
                "opening_time",
                "closing_time",
                "writer_epoch",
            ):
                field = Branch._meta.get_field(key)
                setattr(b, key, field.to_python(branch_data[key]))
            b.save(
                update_fields=[
                    "name",
                    "code",
                    "mode",
                    "hub_url",
                    "simple_mode",
                    "opening_time",
                    "closing_time",
                    "writer_epoch",
                ]
            )
        from catalog.models import SupplyType
        from people.models import Staff

        Staff.objects.update(active=False)
        # Temporarily relax local names before importing a cloud conflict pair.
        SupplyType.objects.filter(archived_at=None).update(needs_merge=True)
        imported_supplies = set()
        for record in document["records"]:
            if record["model"] not in CATALOG:
                raise ValidationError("Invalid configuration record.")
            apply_record(record, b, upward=False)
            if record["model"] == "catalog.supplytype":
                imported_supplies.add(record["fields"]["id"])
        for supply in SupplyType.objects.filter(archived_at=None).exclude(
            pk__in=imported_supplies
        ):
            supply.needs_merge = (
                SupplyType.objects.filter(
                    name__iexact=supply.name, archived_at=None, needs_merge=False
                )
                .exclude(pk=supply.pk)
                .exists()
            )
            supply.save(update_fields=["needs_merge"])
        if initial:
            for record in document["operations"]:
                apply_record(record, b, upward=False)
            for data in document["events"]:
                event = Event(**decode(Event, data))
                if event.branch_id != b.pk or event.shop_id != shop.pk:
                    raise ValidationError("Foreign bootstrap event.")
                event.save_base(raw=True, force_insert=True)
        replica.writer_active = (
            bool(document.get("active")) and b.mode == "hub" and not replica.frozen
        )
        replica.save(update_fields=["writer_active"])
        return b
