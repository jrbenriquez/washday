from django.db import models
from django.core.exceptions import ValidationError
from core.models import TenantModel, TenantManager


class ImmutableQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Historical records are immutable")

    def delete(self):
        raise ValidationError("Historical records are immutable")

    def bulk_update(self, *args, **kwargs):
        raise ValidationError("Historical records are immutable")


class ImmutableManager(TenantManager.from_queryset(ImmutableQuerySet)):
    pass


class ImmutableModel(TenantModel):
    objects = ImmutableManager()
    unscoped = models.Manager.from_queryset(ImmutableQuerySet)()

    class Meta(TenantModel.Meta):
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Historical records are immutable")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Historical records are immutable")


class Event(ImmutableModel):
    branch = models.ForeignKey("core.Branch", on_delete=models.PROTECT)
    seq = models.PositiveBigIntegerField()
    type = models.CharField(max_length=80)
    payload = models.JSONField()
    actor_staff = models.ForeignKey("people.Staff", null=True, on_delete=models.PROTECT)
    occurred_at = models.DateTimeField()
    received_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True)

    class Meta(ImmutableModel.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["branch", "seq"], name="event_branch_sequence"
            )
        ]
