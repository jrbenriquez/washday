import uuid
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from .tenancy import current_shop


class TenantManager(models.Manager):
    def get_queryset(self):
        shop = current_shop()
        return (
            super().get_queryset().filter(shop_id=shop)
            if shop
            else super().get_queryset().none()
        )


class UUIDModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class Shop(UUIDModel):
    name = models.CharField(max_length=160)
    code = models.CharField(max_length=40, unique=True)
    logo = models.CharField(max_length=240, default="img/logo-header.png")
    timezone = models.CharField(max_length=40, default="Asia/Manila")
    created_at = models.DateTimeField(auto_now_add=True)
    archived_at = models.DateTimeField(null=True, blank=True)


class TenantModel(UUIDModel):
    shop = models.ForeignKey(Shop, on_delete=models.PROTECT)
    objects = TenantManager()
    unscoped = models.Manager()

    class Meta:
        abstract = True
        default_manager_name = "objects"
        base_manager_name = "objects"

    def save(self, *args, **kwargs):
        if current_shop() != self.shop_id:
            raise ValidationError("Current shop does not match record")
        # Foreign keys must never bridge shops, including operator-created fixtures.
        for f in self._meta.fields:
            if f.is_relation and f.name != "shop" and getattr(self, f.attname, None):
                model = f.remote_field.model
                if issubclass(model, TenantModel):
                    if not model.unscoped.filter(
                        pk=getattr(self, f.attname), shop_id=self.shop_id
                    ).exists():
                        raise ValidationError("Related record is outside this shop")
        return super().save(*args, **kwargs)


class Branch(TenantModel):
    name = models.CharField(max_length=120)
    code = models.CharField(max_length=30)
    number = models.PositiveIntegerField()
    mode = models.CharField(max_length=10, default="direct")
    simple_mode = models.BooleanField(default=True)
    opening_time = models.TimeField(null=True)
    closing_time = models.TimeField(null=True)
    job_seq = models.PositiveIntegerField(default=0)
    event_seq = models.PositiveBigIntegerField(default=0)

    class Meta(TenantModel.Meta):
        constraints = [
            models.UniqueConstraint(fields=["shop", "number"], name="branch_number"),
            models.UniqueConstraint(fields=["shop", "code"], name="branch_code"),
        ]

    def save(self, *args, **kwargs):
        if self._state.adding and not self.job_seq:
            self.job_seq = self.number * 1000
        elif not self._state.adding:
            # Counters are reserved with atomic F updates; stale settings instances cannot rewind them.
            fields = kwargs.get("update_fields")
            kwargs["update_fields"] = (
                [
                    f.name
                    for f in self._meta.concrete_fields
                    if not f.primary_key
                    and f.name not in ("job_seq", "event_seq", "shop")
                ]
                if fields is None
                else [f for f in fields if f not in ("job_seq", "event_seq")]
            )
        return super().save(*args, **kwargs)


def default_pin_actions():
    return ["payment", "claim", "override"]


class Settings(TenantModel):
    min_kg = models.DecimalField(max_digits=6, decimal_places=1, default=0)
    kg_per_load = models.DecimalField(max_digits=6, decimal_places=1, default=1)
    version = models.PositiveIntegerField(default=1)
    check_after_min = models.PositiveIntegerField(default=90)
    staff_can_add_supply = models.BooleanField(default=False)
    pin_enabled = models.BooleanField(default=True)
    pin_actions = models.JSONField(default=default_pin_actions)

    class Meta(TenantModel.Meta):
        constraints = [models.UniqueConstraint(fields=["shop"], name="one_settings")]


class JobStage(TenantModel):
    name = models.CharField(max_length=80)
    sort_order = models.PositiveIntegerField()
    is_first = models.BooleanField(default=False)
    is_last = models.BooleanField(default=False)
    ask_for_machine = models.BooleanField(default=False)
    machine_category = models.ForeignKey(
        "core.MachineCategory", null=True, on_delete=models.PROTECT
    )
    show_in_simple_mode = models.BooleanField(default=False)
    move_on_when_unloaded = models.BooleanField(default=False)
    archived_at = models.DateTimeField(null=True)


class MachineCategory(TenantModel):
    name = models.CharField(max_length=80)
    label_prefix = models.CharField(max_length=20)
    uses_wash_supplies = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)
    archived_at = models.DateTimeField(null=True)


class Machine(TenantModel):
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT)
    category = models.ForeignKey(MachineCategory, on_delete=models.PROTECT)
    label = models.CharField(max_length=40)
    out_of_service = models.BooleanField(default=False)
    archived_at = models.DateTimeField(null=True)

    class Meta(TenantModel.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["branch", "label"], name="machine_branch_label"
            )
        ]


class ShopOwner(TenantModel):
    email = models.EmailField()
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT
    )
    active = models.BooleanField(default=True)

    class Meta(TenantModel.Meta):
        constraints = [
            models.UniqueConstraint(
                models.functions.Lower("email"), name="owner_email_ci"
            )
        ]
