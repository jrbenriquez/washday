from django.db import models
from core.models import TenantModel


class Customer(TenantModel):
    name = models.CharField(max_length=120)
    phone = models.CharField(max_length=40, blank=True)
