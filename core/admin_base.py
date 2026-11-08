"""Cross-shop inspection for platform operators; mutations use application services."""

import json
from uuid import UUID

from django.contrib import admin
from django.db import models
from django.utils.html import format_html

from .models import Shop

SECRET_FIELDS = frozenset({"pin_hash", "key_hash", "code_hash"})


def redact(value):
    if isinstance(value, dict):
        return {
            key: "[redacted]" if key.casefold() in SECRET_FIELDS else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


class ShopFilter(admin.SimpleListFilter):
    title = "shop"
    parameter_name = "shop_id"

    def lookups(self, request, model_admin):
        return Shop.objects.order_by("code").values_list("pk", "code")

    def queryset(self, request, queryset):
        if self.value():
            try:
                shop_id = UUID(self.value())
            except ValueError:
                return queryset.none()
            return queryset.filter(shop_id=shop_id)
        return queryset


class InspectionAdmin(admin.ModelAdmin):
    actions = None
    list_per_page = 50

    def get_queryset(self, request):
        manager = getattr(self.model, "unscoped", self.model._default_manager)
        # Admin has no current shop. Explicit joins also make tenant FK details
        # available without consulting their scoped base managers.
        related = [field.name for field in self.model._meta.fields if field.is_relation]
        return manager.get_queryset().select_related(*related)

    def get_fields(self, request, obj=None):
        return [
            "safe_" + field.name
            if isinstance(field, models.JSONField)
            and field.name in ("payload", "frame", "changes")
            else field.name
            for field in self.model._meta.fields
            if field.name not in SECRET_FIELDS
        ]

    def get_readonly_fields(self, request, obj=None):
        return self.get_fields(request, obj)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="Shop", ordering="shop__code")
    def shop_code(self, obj):
        return obj.shop.code

    @admin.display(description="Branch", ordering="branch__name")
    def branch_name(self, obj):
        return obj.branch.name

    def json_detail(self, value):
        return format_html(
            "<pre>{}</pre>", json.dumps(redact(value), indent=2, ensure_ascii=False)
        )

    @admin.display(description="Payload")
    def safe_payload(self, obj):
        return self.json_detail(obj.payload)

    @admin.display(description="Frame")
    def safe_frame(self, obj):
        return self.json_detail(obj.frame)

    @admin.display(description="Changes")
    def safe_changes(self, obj):
        return self.json_detail(obj.changes)


class TenantInspectionAdmin(InspectionAdmin):
    list_display = ("id", "shop_code")
    list_filter = (ShopFilter,)
    search_fields = ("=id", "shop__code", "shop__name")
