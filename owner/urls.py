from django.urls import path
from . import views, supply_merge
from . import workspace, reports, onboarding

urlpatterns = [
    path("onboarding/", onboarding.setup, name="owner_onboarding"),
    path("onboarding/device/", onboarding.device, name="owner_onboarding_device"),
    path("supplies/<uuid:source_id>/merge/", supply_merge.edit, name="owner_supply_merge"),
    path("", views.home, name="owner_home"),
    path("dashboard/", workspace.dashboard, name="owner_dashboard"),
    path("theme/", workspace.theme, name="owner_theme"),
    path("live/", workspace.live, name="owner_live"),
    path("branches/", workspace.live, name="owner_branches"),
    path("branches/manage/", workspace.branches, name="owner_branch_manage"),
    path("branches/new/", workspace.branch_edit, name="owner_branch_new"),
    path(
        "branches/<uuid:branch_id>/edit/",
        workspace.branch_edit,
        name="owner_branch_edit",
    ),
    path("staff/", workspace.staff, name="owner_staff"),
    path("machines/", workspace.machines, name="owner_machines"),
    path("reports/sales.xlsx", reports.sales, name="owner_sales_export"),
    path("counts/<uuid:branch_id>/", workspace.counts, name="owner_counts"),
    path("supply-policy/", workspace.supply_policy, name="owner_supply_policy"),
    path("operations/", workspace.operations, name="owner_operations"),
    path(
        "branches/<uuid:branch_id>/mode/",
        workspace.branch_mode,
        name="owner_branch_mode",
    ),
    path("edit/<slug:kind>/", workspace.edit, name="owner_record_new"),
    path(
        "edit/<slug:kind>/<uuid:record_id>/", workspace.edit, name="owner_record_edit"
    ),
    path("login/", views.login, name="owner_login"),
    path("settings/", workspace.settings_page, name="owner_shop_settings"),
    path("staff/new/", views.staff_new, name="owner_staff_new"),
    path("staff/<uuid:staff_id>/", views.staff_update, name="owner_staff_update"),
    path("devices/new/", views.device_new, name="owner_device_new"),
    path("devices/<uuid:device_id>/assign/", views.device_assign, name="owner_device_assign"),
    path("devices/<uuid:device_id>/code/", views.device_code, name="owner_device_code"),
    path(
        "devices/<uuid:device_id>/revoke/",
        views.device_revoke,
        name="owner_device_revoke",
    ),
    path("branches/<uuid:branch_id>/hours/", views.hours, name="owner_hours"),
    path("pin-rules/", views.policy, name="owner_pin_rules"),
]
