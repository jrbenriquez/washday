from django.contrib import admin

from core.admin_base import ShopFilter, TenantInspectionAdmin

from .models import StockCount, StockCountLine, StockEntry, SupplyRequest


@admin.register(StockEntry)
class StockEntryAdmin(TenantInspectionAdmin):
    list_display = (
        "id",
        "shop_code",
        "branch_name",
        "supply_type__name",
        "qty",
        "reason",
        "at",
    )
    search_fields = (
        *TenantInspectionAdmin.search_fields,
        "supply_type__name",
        "=job__number",
    )
    list_filter = (ShopFilter, "reason", "at")
    ordering = ("-at",)


@admin.register(StockCount)
class StockCountAdmin(TenantInspectionAdmin):
    list_display = ("id", "shop_code", "branch_name", "at", "partial")
    list_filter = (ShopFilter, "partial", "at")
    ordering = ("-at",)


@admin.register(StockCountLine)
class StockCountLineAdmin(TenantInspectionAdmin):
    list_display = (
        "id",
        "shop_code",
        "count",
        "supply_type__name",
        "expected",
        "counted",
        "variance",
    )
    search_fields = (*TenantInspectionAdmin.search_fields, "supply_type__name")


@admin.register(SupplyRequest)
class SupplyRequestAdmin(TenantInspectionAdmin):
    list_display = ("name", "shop_code", "branch_name", "status", "created_at")
    search_fields = (*TenantInspectionAdmin.search_fields, "name", "note")
    list_filter = (ShopFilter, "status")
