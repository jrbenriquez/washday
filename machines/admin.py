from django.contrib import admin

from core.admin_base import ShopFilter, TenantInspectionAdmin

from .models import Load


@admin.register(Load)
class LoadAdmin(TenantInspectionAdmin):
    list_display = (
        "id",
        "shop_code",
        "branch_name",
        "machine__label",
        "self_service",
        "started_at",
        "ended_at",
    )
    search_fields = (
        *TenantInspectionAdmin.search_fields,
        "machine__label",
        "=job__number",
    )
    list_filter = (ShopFilter, "self_service", "ended_at")
    ordering = ("-started_at",)
