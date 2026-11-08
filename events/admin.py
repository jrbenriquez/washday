from django.contrib import admin

from core.admin_base import ShopFilter, TenantInspectionAdmin

from .models import (
    Action,
    ConfigurationAudit,
    Event,
    HubCredential,
    Inbox,
    Outbox,
    Replica,
)


@admin.register(Event)
class EventAdmin(TenantInspectionAdmin):
    list_display = ("seq", "shop_code", "branch_name", "type", "occurred_at", "sent_at")
    search_fields = (*TenantInspectionAdmin.search_fields, "type", "=seq")
    list_filter = (ShopFilter, "type", "sent_at")
    ordering = ("-occurred_at",)


@admin.register(Action)
class ActionAdmin(TenantInspectionAdmin):
    list_display = ("id", "shop_code", "branch_name", "kind", "created_at", "undone_at")
    list_filter = (ShopFilter, "kind", "undone_at")


@admin.register(Outbox)
class OutboxAdmin(TenantInspectionAdmin):
    list_display = ("id", "shop_code", "event__seq", "sent_at")
    list_filter = (ShopFilter, "sent_at")


@admin.register(HubCredential)
class HubCredentialAdmin(TenantInspectionAdmin):
    list_display = ("id", "shop_code", "branch_name", "state", "epoch", "last_seen_at")
    list_filter = (ShopFilter, "state")


@admin.register(ConfigurationAudit)
class ConfigurationAuditAdmin(TenantInspectionAdmin):
    list_display = ("id", "shop_code", "branch_name", "kind", "at")
    search_fields = (*TenantInspectionAdmin.search_fields, "kind")
    list_filter = (ShopFilter, "kind", "at")
    ordering = ("-at",)


@admin.register(Replica)
class ReplicaAdmin(TenantInspectionAdmin):
    list_display = (
        "id",
        "shop_code",
        "branch_name",
        "acknowledged_seq",
        "writer_active",
        "frozen",
        "failures",
    )
    list_filter = (ShopFilter, "writer_active", "frozen")


@admin.register(Inbox)
class InboxAdmin(TenantInspectionAdmin):
    list_display = ("seq", "shop_code", "branch_name", "event_id", "applied_at")
    search_fields = (*TenantInspectionAdmin.search_fields, "=event_id", "=seq")
    list_filter = (ShopFilter, "applied_at")
