from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from django.http import Http404
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.utils import timezone
from core.models import Machine, Settings, JobStage
from catalog.models import Service
from jobs.models import Job
from jobs.views import require_branch
from jobs.transitions import next_stage, StaleAction
from .models import Load
from .services import start_for_job, self_service, unload


def full_branch(request):
    b = require_branch(request)
    if b.simple_mode:
        raise Http404()
    return b


def tiles(branch, target=None):
    rows = []
    limit = Settings.objects.get(shop_id=branch.shop_id).check_after_min
    machines = (
        Machine.objects.filter(
            branch=branch, archived_at=None, category__archived_at=None
        )
        .select_related("category")
        .order_by("category__sort_order", "label")
    )
    if target and target.machine_category_id:
        machines = machines.filter(category_id=target.machine_category_id)
    for m in machines:
        load = (
            Load.objects.filter(machine=m, ended_at=None)
            .select_related("job__status")
            .first()
        )
        last = (
            Load.objects.filter(machine=m, ended_at__isnull=False)
            .order_by("-ended_at")
            .first()
        )
        elapsed = (
            max(0, int((timezone.now() - load.started_at).total_seconds() // 60))
            if load
            else 0
        )
        rows.append(
            {
                "machine": m,
                "load": load,
                "elapsed": elapsed,
                "flag": bool(load and elapsed >= limit),
                "last": last,
                "last_duration": max(
                    0, int((last.ended_at - last.started_at).total_seconds() // 60)
                )
                if last
                else None,
                "available": not load and not m.out_of_service,
                "loads_today": Load.objects.filter(
                    machine=m, started_at__date=timezone.localdate()
                ).count(),
            }
        )
    return rows


@require_GET
def grid(request):
    branch = full_branch(request)
    return render(
        request,
        "machines/grid.html",
        {
            "tiles": tiles(branch),
            "self_services": Service.objects.filter(archived_at=None, mode="load"),
        },
    )


@require_http_methods(["GET", "POST"])
def picker(request, number):
    branch = full_branch(request)
    job = get_object_or_404(
        Job.objects.select_related("status"), branch=branch, number=number
    )
    if job.paper_ref:
        raise Http404()
    target_id = (
        request.POST.get("target")
        if request.method == "POST"
        else request.GET.get("target")
    )
    target = get_object_or_404(
        JobStage, pk=target_id, ask_for_machine=True, archived_at=None
    )
    nxt = next_stage(job, branch)
    if (
        request.method == "GET"
        and target.pk != job.status_id
        and (not nxt or target.pk != nxt.pk)
    ):
        raise Http404()
    error = None
    if request.method == "POST":
        try:
            load = start_for_job(
                branch,
                number,
                request.POST.get("expected"),
                target.id,
                request.POST.get("machine"),
                request.staff,
            )
            messages.success(request, f"Job #{number} started in {load.machine.label}.")
            return redirect("board")
        except StaleAction as e:
            messages.error(request, " ".join(e.messages))
            return redirect("board")
        except ValidationError as e:
            error = " ".join(e.messages)
    return render(
        request,
        "machines/picker.html",
        {"job": job, "target": target, "tiles": tiles(branch, target), "error": error},
        status=422 if error else 200,
    )


@require_http_methods(["GET", "POST"])
def start_self(request, machine_id):
    branch = full_branch(request)
    machine = get_object_or_404(
        Machine,
        pk=machine_id,
        branch=branch,
        archived_at=None,
        category__archived_at=None,
    )
    if (
        machine.out_of_service
        or Load.objects.filter(machine=machine, ended_at=None).exists()
    ):
        messages.error(
            request,
            f"{machine.label} is unavailable. Monitor the current load on Machines.",
        )
        return redirect("machines")
    services = Service.objects.filter(archived_at=None, mode="load")
    if not services.exists():
        raise Http404()
    error = None
    if request.method == "POST":
        # This endpoint can never start/link/create a Job. Job starts belong to the board.
        if any(request.POST.get(k) for k in ("job", "job_id", "number")):
            raise Http404()
        try:
            self_service(
                branch,
                machine_id,
                request.POST.get("service"),
                request.POST.get("pay_method"),
                request.staff,
            )
            messages.success(request, f"Self-service started in {machine.label}.")
            return redirect("machines")
        except ValidationError as e:
            error = " ".join(e.messages)
    return render(
        request,
        "machines/selfservice.html",
        {"machine": machine, "services": services, "error": error},
        status=422 if error else 200,
    )


@require_POST
def finish(request, machine_id):
    branch = full_branch(request)
    try:
        load = unload(
            branch, machine_id, request.POST.get("expected_load"), request.staff
        )
        minutes = max(0, int((load.ended_at - load.started_at).total_seconds() // 60))
        messages.success(
            request, f"{load.machine.label}: Unloaded after {minutes} min."
        )
    except ValidationError as e:
        messages.error(request, " ".join(e.messages))
    return redirect("machines")
