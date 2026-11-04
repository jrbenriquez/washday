from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from people import views as people
from owner import views as owner
from jobs import views, board, history
from machines import views as machines
from supplies import views as supplies

urlpatterns = [
    path("owner/", include("owner.urls")),
    path("accounts/login/", owner.account_login, name="local_account_login"),
    path("accounts/signup/", owner.unavailable),
    re_path(r"^accounts/password/", owner.unavailable),
    path("accounts/", include("allauth.urls")),
    path("device/start/", people.start, name="device_start"),
    path("device/setup/", people.setup, name="device_setup"),
    path("device/manifest.webmanifest", people.manifest, name="device_manifest"),
    path("shift/", people.shift, name="shift"),
    path("shift/end/", people.end, name="shift_end"),
    path("supplies/", supplies.index, name="supplies"),
    path(
        "supplies/receive/", supplies.action, {"kind": "receive"}, name="stock_receive"
    ),
    path("supplies/count/", supplies.action, {"kind": "count"}, name="stock_count"),
    path(
        "supplies/request/", supplies.action, {"kind": "request"}, name="supply_request"
    ),
    path("supplies/types/new/", supplies.new_type, name="supply_type_new"),
    path("machines/", machines.grid, name="machines"),
    path("machines/<uuid:machine_id>/start/", machines.start_self, name="self_service"),
    path("machines/<uuid:machine_id>/unload/", machines.finish, name="unload"),
    path("jobs/<int:number>/machine/", machines.picker, name="machine_picker"),
    path("jobs/<int:number>/history/", history.timeline, name="timeline"),
    path("jobs/", board.board, name="board"),
    path("jobs/<int:number>/advance/", board.move, name="advance"),
    path("jobs/<int:number>/stage/", board.edit, name="edit_stage"),
    path("jobs/<int:number>/claim/", board.release, name="claim"),
    path("", people.home, name="home"),
    path("jobs/new/", views.new, name="new"),
    path("jobs/price/", views.price, name="price"),
    path("customers/search/", views.customers, name="customer_search"),
    path("jobs/<int:number>/", views.stub, name="stub"),
    path("theme/", views.theme, name="theme"),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
