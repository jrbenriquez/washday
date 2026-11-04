from django.urls import path
from . import views

urlpatterns = [
    path("", views.settings_page, name="drive_exports"),
    path("connect/", views.connect, name="drive_connect"),
    path("callback/", views.callback, name="drive_callback"),
    path("folder/", views.folder, name="drive_folder"),
    path("picker-token/", views.picker_token, name="drive_picker_token"),
    path("export-now/", views.export_now, name="drive_export_now"),
    path("disconnect/", views.disconnect, name="drive_disconnect"),
]
