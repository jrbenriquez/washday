from django.contrib import admin

from core.admin_base import ShopFilter, TenantInspectionAdmin

from .models import Job, JobLine


@admin.register(Job)
class JobAdmin(TenantInspectionAdmin):
    list_display = (
        "number",
        "shop_code",
        "branch_name",
        "total",
        "received_at",
        "paid_at",
        "claimed_at",
    )
    search_fields = (
        *TenantInspectionAdmin.search_fields,
        "=number",
        "customer__name",
        "paper_ref",
    )
    list_filter = (ShopFilter, "paid_at", "claimed_at", "received_at")
    ordering = ("-received_at",)


@admin.register(JobLine)
class JobLineAdmin(TenantInspectionAdmin):
    list_display = ("label", "shop_code", "job__number", "kind", "amount")
    search_fields = (*TenantInspectionAdmin.search_fields, "label", "=job__number")
    list_filter = (ShopFilter, "kind")
