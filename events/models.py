from django.core.exceptions import ValidationError
from django.db import models

from core.models import TenantManager, TenantModel


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
    device = models.ForeignKey("people.Device", null=True, on_delete=models.PROTECT)
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


class Action(TenantModel):
    """One transaction's undo receipt; Events and count history stay immutable."""

    branch = models.ForeignKey("core.Branch", on_delete=models.PROTECT)
    device = models.ForeignKey("people.Device", null=True, on_delete=models.PROTECT)
    staff = models.ForeignKey("people.Staff", null=True, on_delete=models.PROTECT)
    event = models.OneToOneField(Event, on_delete=models.PROTECT)
    first_seq = models.PositiveBigIntegerField()
    kind = models.CharField(max_length=40)
    changes = models.JSONField()
    created_at = models.DateTimeField()
    undone_at = models.DateTimeField(null=True)


class Outbox(TenantModel):
    event = models.OneToOneField(Event, on_delete=models.PROTECT)
    frame = models.JSONField()
    sent_at = models.DateTimeField(null=True)

    class Meta(TenantModel.Meta):
        verbose_name = "outbox entry"
        verbose_name_plural = "outbox entries"


class HubCredential(TenantModel):
    branch = models.OneToOneField("core.Branch", on_delete=models.PROTECT)
    key_hash = models.CharField(max_length=64, unique=True)
    epoch = models.PositiveIntegerField()
    state = models.CharField(max_length=12, default="prepared")
    bootstrap_seq = models.PositiveBigIntegerField(null=True)
    last_seen_at = models.DateTimeField(null=True)


class ConfigurationAudit(ImmutableModel):
    """Cloud administration must not consume a hub's operational sequence."""

    branch = models.ForeignKey("core.Branch", on_delete=models.PROTECT)
    kind = models.CharField(max_length=80)
    payload = models.JSONField()
    at = models.DateTimeField()


class Replica(TenantModel):
    """Durable local cursor and write fence, retained across process restarts."""

    branch = models.OneToOneField("core.Branch", on_delete=models.PROTECT)
    acknowledged_seq = models.PositiveBigIntegerField(default=0)
    writer_active = models.BooleanField(default=False)
    frozen = models.BooleanField(default=False)
    failures = models.PositiveIntegerField(default=0)
    push_due = models.DateTimeField(null=True)
    pull_due = models.DateTimeField(null=True)


class Inbox(TenantModel):
    branch = models.ForeignKey("core.Branch", on_delete=models.PROTECT)
    event_id = models.UUIDField(unique=True)
    seq = models.PositiveBigIntegerField()
    frame = models.JSONField()
    digest = models.CharField(max_length=64)
    applied_at = models.DateTimeField(null=True)

    class Meta(TenantModel.Meta):
        verbose_name = "inbox entry"
        verbose_name_plural = "inbox entries"
        constraints = [
            models.UniqueConstraint(fields=["branch", "seq"], name="inbox_branch_seq")
        ]
