from django.contrib import admin

from core.admin_base import TenantInspectionAdmin

from .models import Customer


@admin.register(Customer)
class CustomerAdmin(TenantInspectionAdmin):
    list_display = ("name", "shop_code", "phone")
    search_fields = (*TenantInspectionAdmin.search_fields, "name", "phone")
