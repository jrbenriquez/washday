from people.guards import pin_guard
from decimal import Decimal
from django.shortcuts import render, redirect
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.utils import timezone
from django.db.models import Sum
from catalog.models import SupplyType
from core.models import Settings
from jobs.views import require_branch
from .models import StockEntry, StockCount, StockCountLine, SupplyRequest
from .services import balance, receive, count_stock, request_supply, add_type


def context(request):
    b = require_branch(request)
    rows = []
    for supply in SupplyType.objects.filter(archived_at=None).order_by("name"):
        amount = balance(b, supply)
        used = StockEntry.objects.filter(
            branch=b,
            supply_type=supply,
            qty__lt=0,
            at__date=timezone.localdate(),
            reason__in=["washer_load", "packed_job", "addon"],
        ).aggregate(total=Sum("qty"))["total"] or Decimal("0")
        latest = (
            StockCountLine.objects.filter(count__branch=b, supply_type=supply)
            .order_by("-count__at")
            .first()
        )
        variance = latest.variance if latest else None
        severity = (
            "crit"
            if variance is not None and abs(variance) > 3
            else "warn"
            if variance is not None and abs(variance) >= 1
            else "plain"
        )
        rows.append(
            {
                "supply": supply,
                "balance": amount,
                "used": -used,
                "low": amount <= supply.low_level,
                "variance": variance,
                "latest": latest,
                "severity": severity,
            }
        )
    entries = (
        StockEntry.objects.filter(branch=b)
        .select_related("supply_type", "job")
        .order_by("-at", "-id")
    )
    return {
        "stocks": rows,
        "entries": Paginator(entries, 10).get_page(request.GET.get("page")),
        "can_add": Settings.objects.get(shop_id=b.shop_id).staff_can_add_supply,
        "requests": SupplyRequest.objects.filter(branch=b, status="open").order_by(
            "-created_at"
        ),
        "counts": StockCount.objects.filter(branch=b)
        .select_related("by")
        .order_by("-at")[:10],
    }


@require_GET
def index(request):
    return render(request, "supplies/index.html", context(request))


@require_POST
def action(request, kind):
    b = require_branch(request)
    gate = pin_guard(request, kind)
    if gate is not None:
        return gate
    try:
        if kind == "receive":
            receive(
                b,
                request.POST.get("supply_type"),
                request.POST.get("qty"),
                request.staff,
            )
            message = "Stock received."
        elif kind == "count":
            count_stock(b, request.POST, request.staff)
            message = "Stock count saved."
        elif kind == "request":
            request_supply(
                b,
                request.POST.get("name", ""),
                request.POST.get("note", ""),
                request.staff,
            )
            message = "Supply request sent to the owner."
        else:
            raise ValidationError("Unknown supply action.")
        messages.success(request, message)
        return redirect("supplies")
    except ValidationError as e:
        c = context(request)
        c["error"] = " ".join(e.messages)
        return render(request, "supplies/index.html", c, status=422)


@require_http_methods(["GET", "POST"])
def new_type(request):
    b = require_branch(request)
    if request.method == "POST":
        gate = pin_guard(request, "add_type")
        if gate is not None:
            return gate
        try:
            add_type(b, request.POST, request.staff)
            messages.success(request, "Supply type added.")
            return redirect("supplies")
        except ValidationError as e:
            return render(
                request,
                "supplies/new.html",
                {"error": " ".join(e.messages)},
                status=422,
            )
    from django.core.exceptions import PermissionDenied

    if not Settings.objects.get(shop_id=b.shop_id).staff_can_add_supply:
        raise PermissionDenied()
    return render(request, "supplies/new.html")
