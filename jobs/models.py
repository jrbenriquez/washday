from django.db import models
from core.models import TenantModel
from events.models import ImmutableModel


class Job(TenantModel):
    branch = models.ForeignKey("core.Branch", on_delete=models.PROTECT)
    number = models.PositiveIntegerField()
    customer = models.ForeignKey(
        "customers.Customer", null=True, on_delete=models.PROTECT
    )
    service = models.ForeignKey("catalog.Service", null=True, on_delete=models.PROTECT)
    kg = models.DecimalField(max_digits=6, decimal_places=1)
    pieces = models.JSONField(default=list)
    fees = models.JSONField(default=list)
    notes = models.TextField(blank=True)
    status = models.ForeignKey("core.JobStage", null=True, on_delete=models.PROTECT)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    received_at = models.DateTimeField()
    paid_at = models.DateTimeField(null=True)
    pay_method = models.CharField(max_length=10, blank=True)
    pay_ref = models.CharField(max_length=120, blank=True)
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    claimed_at = models.DateTimeField(null=True)
    ready_at = models.DateTimeField(null=True)
    first_ready_at = models.DateTimeField(null=True)
    created_by = models.ForeignKey("people.Staff", null=True, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    paper_ref = models.CharField(max_length=30, blank=True)
    paper_date = models.DateField(null=True)
    written_total = models.DecimalField(max_digits=10, decimal_places=2, null=True)

    class Meta(TenantModel.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["branch", "number"], name="job_branch_number"
            ),
            models.UniqueConstraint(
                fields=["branch", "paper_date", "paper_ref"],
                condition=~models.Q(paper_ref=""),
                name="job_paper_reference",
            ),
        ]


class JobLine(ImmutableModel):
    job = models.ForeignKey(Job, on_delete=models.PROTECT, related_name="lines")
    label = models.CharField(max_length=240)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    kind = models.CharField(max_length=10)
