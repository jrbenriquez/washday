from django.contrib import admin

from core.admin_base import ShopFilter, TenantInspectionAdmin

from .models import Device, DeviceSetupCode, Shift, Staff


@admin.register(Staff)
class StaffAdmin(TenantInspectionAdmin):
    list_display = ("name", "shop_code", "branch_name", "active")
    search_fields = (*TenantInspectionAdmin.search_fields, "name", "branch__name")
    list_filter = (ShopFilter, "active")


@admin.register(Device)
class DeviceAdmin(TenantInspectionAdmin):
    list_display = (
        "name",
        "shop_code",
        "branch_name",
        "kind",
        "last_seen_at",
        "revoked_at",
    )
    search_fields = (*TenantInspectionAdmin.search_fields, "name", "branch__name")
    list_filter = (ShopFilter, "kind", "revoked_at")


@admin.register(DeviceSetupCode)
class DeviceSetupCodeAdmin(TenantInspectionAdmin):
    list_display = ("id", "shop_code", "device__name", "expires_at", "used_at")
    search_fields = (*TenantInspectionAdmin.search_fields, "device__name")
    list_filter = (ShopFilter, "used_at")


@admin.register(Shift)
class ShiftAdmin(TenantInspectionAdmin):
    list_display = (
        "id",
        "shop_code",
        "staff__name",
        "device__name",
        "started_at",
        "ends_at",
        "ended_at",
    )
    search_fields = (
        *TenantInspectionAdmin.search_fields,
        "staff__name",
        "device__name",
    )
    list_filter = (ShopFilter, "ended_at")
    ordering = ("-started_at",)
