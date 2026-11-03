from django.db import models
from core.models import TenantModel


class Staff(TenantModel):
    branch = models.ForeignKey("core.Branch", on_delete=models.PROTECT)
    name = models.CharField(max_length=120)
    pin_hash = models.CharField(max_length=256)
    active = models.BooleanField(default=True)
