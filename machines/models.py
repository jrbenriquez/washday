from django.db import models
from django.db.models import Q
from core.models import TenantModel


class Load(TenantModel):
    branch = models.ForeignKey("core.Branch", on_delete=models.PROTECT)
    machine = models.ForeignKey("core.Machine", on_delete=models.PROTECT)
    job = models.ForeignKey("jobs.Job", null=True, on_delete=models.PROTECT)
    self_service = models.BooleanField(default=False)
    stage = models.ForeignKey("core.JobStage", null=True, on_delete=models.PROTECT)
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True)
    cancelled_at = models.DateTimeField(null=True)
    started_by = models.ForeignKey(
        "people.Staff", null=True, on_delete=models.PROTECT, related_name="+"
    )
    ended_by = models.ForeignKey(
        "people.Staff", null=True, on_delete=models.PROTECT, related_name="+"
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    pay_method = models.CharField(max_length=10, blank=True)

    class Meta(TenantModel.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["machine"],
                condition=Q(ended_at=None),
                name="one_open_machine_load",
            )
        ]
