import uuid

from django.db import models


class Inquiry(models.Model):
    class Type(models.TextChoices):
        CUSTOM = "custom", "Custom inquiry"
        DEMO = "demo", "Demo request"

    class Status(models.TextChoices):
        NEW = "new", "New"
        CONTACTED = "contacted", "Contacted"
        SCHEDULED = "scheduled", "Demo scheduled"
        CLOSED = "closed", "Closed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    submission_id = models.UUIDField(unique=True, editable=False)
    type = models.CharField(max_length=6, choices=Type.choices)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.NEW)
    name = models.CharField(max_length=120)
    email = models.EmailField()
    phone = models.CharField(max_length=40, blank=True)
    shop_name = models.CharField(max_length=160, blank=True)
    branch_count = models.PositiveSmallIntegerField(null=True, blank=True)
    availability = models.CharField(max_length=240, blank=True)
    message = models.TextField(max_length=4000, blank=True)
    internal_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(condition=models.Q(type__in=["custom", "demo"]), name="inquiry_valid_type"),
            models.CheckConstraint(condition=models.Q(status__in=["new", "contacted", "scheduled", "closed"]), name="inquiry_valid_status"),
        ]
        verbose_name_plural = "inquiries"

    def __str__(self):
        return f"{self.get_type_display()} · {self.name}"
