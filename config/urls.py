from django.urls import path
from django.views.generic import RedirectView
from jobs import views, board, history
from machines import views as machines
from supplies import views as supplies

urlpatterns = [
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
    path("", RedirectView.as_view(pattern_name="new", permanent=False)),
    path("jobs/new/", views.new, name="new"),
    path("jobs/price/", views.price, name="price"),
    path("customers/search/", views.customers, name="customer_search"),
    path("jobs/<int:number>/", views.stub, name="stub"),
    path("theme/", views.theme, name="theme"),
]
