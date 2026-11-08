from django.contrib import admin

from .admin_base import InspectionAdmin, ShopFilter, TenantInspectionAdmin
from .models import (
    Branch,
    JobStage,
    Machine,
    MachineCategory,
    Settings,
    Shop,
    ShopOwner,
)


@admin.register(Shop)
class ShopAdmin(InspectionAdmin):
    list_display = ("code", "name", "timezone", "created_at", "archived_at")
    search_fields = ("code", "name")
    list_filter = ("archived_at",)


@admin.register(Branch)
class BranchAdmin(TenantInspectionAdmin):
    list_display = ("name", "code", "shop_code", "number", "mode", "simple_mode")
    search_fields = (*TenantInspectionAdmin.search_fields, "name", "code")
    list_filter = (ShopFilter, "mode", "simple_mode")


@admin.register(Settings)
class SettingsAdmin(TenantInspectionAdmin):
    list_display = ("shop_code", "min_kg", "kg_per_load", "version", "pin_enabled")


@admin.register(JobStage)
class JobStageAdmin(TenantInspectionAdmin):
    list_display = (
        "name",
        "shop_code",
        "sort_order",
        "is_first",
        "is_last",
        "archived_at",
    )
    search_fields = (*TenantInspectionAdmin.search_fields, "name")
    ordering = ("shop__code", "sort_order")


@admin.register(MachineCategory)
class MachineCategoryAdmin(TenantInspectionAdmin):
    list_display = (
        "name",
        "shop_code",
        "label_prefix",
        "uses_wash_supplies",
        "archived_at",
    )
    search_fields = (*TenantInspectionAdmin.search_fields, "name", "label_prefix")


@admin.register(Machine)
class MachineAdmin(TenantInspectionAdmin):
    list_display = (
        "label",
        "shop_code",
        "branch_name",
        "out_of_service",
        "archived_at",
    )
    search_fields = (*TenantInspectionAdmin.search_fields, "label", "branch__name")
    list_filter = (ShopFilter, "out_of_service", "archived_at")


@admin.register(ShopOwner)
class ShopOwnerAdmin(TenantInspectionAdmin):
    list_display = ("email", "shop_code", "active", "user")
    search_fields = (*TenantInspectionAdmin.search_fields, "email")
    list_filter = (ShopFilter, "active")
