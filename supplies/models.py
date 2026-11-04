from django.db import models
from core.models import TenantModel
from events.models import ImmutableModel


class StockEntry(ImmutableModel):
    branch = models.ForeignKey("core.Branch", on_delete=models.PROTECT)
    supply_type = models.ForeignKey("catalog.SupplyType", on_delete=models.PROTECT)
    qty = models.DecimalField(max_digits=12, decimal_places=3)
    reason = models.CharField(max_length=30)
    job = models.ForeignKey("jobs.Job", null=True, on_delete=models.PROTECT)
    load = models.ForeignKey("machines.Load", null=True, on_delete=models.PROTECT)
    at = models.DateTimeField()
    by = models.ForeignKey("people.Staff", null=True, on_delete=models.PROTECT)

    class Meta(ImmutableModel.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["job", "supply_type", "reason"],
                condition=models.Q(reason__in=["addon", "packed_job"]),
                name="one_job_supply_deduction",
            ),
            models.UniqueConstraint(
                fields=["load", "supply_type", "reason"],
                condition=models.Q(reason="washer_load"),
                name="one_load_supply_deduction",
            ),
        ]


class StockCount(ImmutableModel):
    @property
    def actor_name(self):
        return (
            self.by.name
            if self.by
            else self.device.name
            if self.device
            else "Development device"
        )

    device = models.ForeignKey("people.Device", null=True, on_delete=models.PROTECT)
    branch = models.ForeignKey("core.Branch", on_delete=models.PROTECT)
    by = models.ForeignKey("people.Staff", null=True, on_delete=models.PROTECT)
    at = models.DateTimeField()
    partial = models.BooleanField(default=False)


class StockCountLine(ImmutableModel):
    count = models.ForeignKey(
        StockCount, on_delete=models.PROTECT, related_name="lines"
    )
    supply_type = models.ForeignKey("catalog.SupplyType", on_delete=models.PROTECT)
    expected = models.DecimalField(max_digits=12, decimal_places=3)
    counted = models.DecimalField(max_digits=12, decimal_places=3)
    variance = models.DecimalField(max_digits=12, decimal_places=3)

    class Meta(ImmutableModel.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["count", "supply_type"], name="count_supply_once"
            )
        ]


class SupplyRequest(TenantModel):
    branch = models.ForeignKey("core.Branch", on_delete=models.PROTECT)
    name = models.CharField(max_length=120)
    note = models.TextField(blank=True)
    requested_by = models.ForeignKey(
        "people.Staff", null=True, on_delete=models.PROTECT
    )
    status = models.CharField(max_length=15, default="open")
    created_at = models.DateTimeField(auto_now_add=True)
