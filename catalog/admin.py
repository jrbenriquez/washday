from django.contrib import admin

from core.admin_base import ShopFilter, TenantInspectionAdmin

from .models import (
    AddOn,
    AddOnUse,
    Fee,
    PieceItem,
    PieceVariant,
    Service,
    SupplyAlias,
    SupplyType,
)


class CatalogAdmin(TenantInspectionAdmin):
    list_display = ("name", "shop_code", "archived_at")
    search_fields = (*TenantInspectionAdmin.search_fields, "name")
    list_filter = (ShopFilter, "archived_at")


@admin.register(Service)
class ServiceAdmin(CatalogAdmin):
    list_display = ("name", "shop_code", "mode", "price", "archived_at")
    list_filter = (ShopFilter, "mode", "archived_at")


@admin.register(AddOn)
class AddOnAdmin(CatalogAdmin):
    list_display = ("name", "shop_code", "price", "archived_at")


@admin.register(Fee)
class FeeAdmin(CatalogAdmin):
    list_display = ("name", "shop_code", "amount", "note", "archived_at")


admin.site.register(PieceItem, CatalogAdmin)


@admin.register(PieceVariant)
class PieceVariantAdmin(TenantInspectionAdmin):
    list_display = ("label", "shop_code", "piece_item__name", "price", "active")
    search_fields = (*TenantInspectionAdmin.search_fields, "label", "piece_item__name")
    list_filter = (ShopFilter, "active")


@admin.register(SupplyType)
class SupplyTypeAdmin(CatalogAdmin):
    list_display = (
        "name",
        "shop_code",
        "unit",
        "low_level",
        "needs_merge",
        "archived_at",
    )
    list_filter = (ShopFilter, "needs_merge", "archived_at")


@admin.register(AddOnUse)
class AddOnUseAdmin(TenantInspectionAdmin):
    list_display = ("id", "shop_code", "addon__name", "supply_type__name", "qty")
    search_fields = (
        *TenantInspectionAdmin.search_fields,
        "addon__name",
        "supply_type__name",
    )


@admin.register(SupplyAlias)
class SupplyAliasAdmin(TenantInspectionAdmin):
    list_display = ("id", "shop_code", "source__name", "target__name")
    search_fields = (
        *TenantInspectionAdmin.search_fields,
        "source__name",
        "target__name",
    )
