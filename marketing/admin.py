from django.contrib import admin

from .models import Inquiry


@admin.register(Inquiry)
class InquiryAdmin(admin.ModelAdmin):
    list_display = ("name", "type", "shop_name", "email", "status", "created_at")
    list_filter = ("type", "status", "created_at")
    search_fields = ("name", "email", "shop_name", "message")
    readonly_fields = ("id", "submission_id", "type", "name", "email", "phone", "shop_name", "branch_count", "availability", "message", "created_at", "updated_at")
    fields = ("status", "internal_notes", *readonly_fields)
    actions = None
    list_per_page = 30

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
