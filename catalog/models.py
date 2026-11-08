from django.db import models
from core.models import TenantModel


class CatalogModel(TenantModel):
    name = models.CharField(max_length=120)
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta(TenantModel.Meta):
        abstract = True


class Service(CatalogModel):
    mode = models.CharField(
        max_length=10, choices=[("kg", "Per kg"), ("load", "Per load")]
    )
    price = models.DecimalField(max_digits=10, decimal_places=2)


class AddOn(CatalogModel):
    price = models.DecimalField(max_digits=10, decimal_places=2)


class Fee(CatalogModel):
    note = models.CharField(max_length=120, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)


class PieceItem(CatalogModel):
    pass


class PieceVariant(TenantModel):
    piece_item = models.ForeignKey(PieceItem, on_delete=models.PROTECT)
    label = models.CharField(max_length=80)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    active = models.BooleanField(default=True)


class SupplyType(CatalogModel):
    needs_merge = models.BooleanField(default=False)
    unit = models.CharField(max_length=30)
    low_level = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    per_washer_load = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    per_packed_job = models.DecimalField(max_digits=12, decimal_places=3, default=0)

    class Meta(CatalogModel.Meta):
        constraints = [
            models.UniqueConstraint(
                models.functions.Lower("name"),
                "shop",
                condition=models.Q(archived_at=None, needs_merge=False),
                name="active_supply_name_ci",
            )
        ]


class AddOnUse(TenantModel):
    addon = models.ForeignKey(AddOn, on_delete=models.PROTECT)
    supply_type = models.ForeignKey(SupplyType, on_delete=models.PROTECT)
    qty = models.DecimalField(max_digits=12, decimal_places=3)

    class Meta(TenantModel.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["addon", "supply_type"], name="addon_supply_recipe"
            )
        ]


class SupplyAlias(TenantModel):
    source = models.OneToOneField(SupplyType, on_delete=models.PROTECT, related_name="alias_source")
    target = models.ForeignKey(SupplyType, on_delete=models.PROTECT, related_name="alias_targets")

    class Meta(TenantModel.Meta):
        verbose_name_plural = "supply aliases"
