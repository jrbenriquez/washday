from people.guards import pin_guard
from django.shortcuts import render, redirect, get_object_or_404
from django.http import Http404
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from django.db.models import Q
from catalog.models import Service, AddOn, Fee, PieceVariant
from customers.models import Customer
from .models import Job
from .services import quote, create_job


def require_branch(request):
    if not getattr(request, "branch", None):
        raise Http404("An enrolled device is required.")
    return request.branch


def form_context(request, data=None):
    require_branch(request)
    return {
        "services": Service.objects.filter(archived_at=None),
        "addons": AddOn.objects.filter(archived_at=None),
        "fees": Fee.objects.filter(archived_at=None),
        "variants": PieceVariant.objects.filter(
            active=True, piece_item__archived_at=None
        ).select_related("piece_item"),
        "paper": request.GET.get("paper") == "1"
        or (data is not None and data.get("paper") == "1"),
        "data": data or {},
        "quote": None,
    }


@require_http_methods(["GET", "POST"])
def new(request):
    ctx = form_context(request, request.POST if request.method == "POST" else None)
    if request.method == "POST":
        gate = pin_guard(
            request,
            "create",
            *(
                ["payment"]
                if request.POST.get("pay_method") in ("cash", "gcash")
                else []
            ),
        )
        if gate is not None:
            return gate
        try:
            job, created = create_job(request.POST, request.branch, request.staff)
            messages.success(
                request,
                f"Job #{job.number} created."
                if created
                else f"Paper reference already entered as job #{job.number}. Opened the existing job.",
            )
            return redirect("stub", number=job.number)
        except ValidationError as e:
            ctx["error"] = " ".join(e.messages)
    return render(
        request, "jobs/new.html", ctx, status=422 if ctx.get("error") else 200
    )


@require_POST
def price(request):
    branch = require_branch(request)
    try:
        q = quote(request.POST, branch)
        if request.POST.get("paper") == "1":
            q["written_total"] = request.POST.get("written_total", "")
        return render(request, "jobs/summary.html", {"quote": q})
    except ValidationError as e:
        return render(request, "jobs/summary.html", {"error": " ".join(e.messages)})


@require_GET
def customers(request):
    require_branch(request)
    query = request.GET.get("customer_search", "").strip()
    found = (
        Customer.objects.filter(
            Q(name__icontains=query) | Q(phone__icontains=query)
        ).order_by("name")[:10]
        if query
        else []
    )
    return render(request, "jobs/customers.html", {"customers": found})


@require_GET
def stub(request, number):
    branch = require_branch(request)
    job = get_object_or_404(
        Job.objects.select_related("customer", "created_by", "status"),
        branch=branch,
        number=number,
    )
    return render(request, "jobs/stub.html", {"job": job, "lines": job.lines.all()})


@require_POST
def theme(request):
    response = redirect("new")
    value = "dark" if request.POST.get("theme") == "dark" else "light"
    response.set_cookie(
        "app_theme", value, max_age=31536000, samesite="Lax", httponly=True
    )
    messages.success(request, f"{value.title()} theme saved.")
    return response
