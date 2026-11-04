from django.urls import path, include
from . import views

urlpatterns = [
    path("drive-exports/", include("backups.urls")),
    path("", views.home, name="owner_home"),
    path("login/", views.login, name="owner_login"),
    path("settings/", views.shop_settings, name="owner_shop_settings"),
    path("staff/new/", views.staff_new, name="owner_staff_new"),
    path("staff/<uuid:staff_id>/", views.staff_update, name="owner_staff_update"),
    path("devices/new/", views.device_new, name="owner_device_new"),
    path("devices/<uuid:device_id>/code/", views.device_code, name="owner_device_code"),
    path(
        "devices/<uuid:device_id>/revoke/",
        views.device_revoke,
        name="owner_device_revoke",
    ),
    path("branches/<uuid:branch_id>/hours/", views.hours, name="owner_hours"),
    path("pin-rules/", views.policy, name="owner_pin_rules"),
]
