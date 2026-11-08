from events.journal import recorded_action
from django.db import transaction
from django.core.exceptions import ValidationError
from django.http import Http404
from django.utils import timezone
from core.models import Branch, Machine, JobStage
from core.operating_hours import require_job_operating_hours
from catalog.models import Service
from jobs.services import append_event, get_active, money
from jobs.transitions import lock_job, next_stage, set_stage
from .models import Load


def active_machine(branch, key):
    m = (
        Machine.objects.select_for_update(of=("self",))
        .filter(pk=key, branch=branch, archived_at=None, category__archived_at=None)
        .first()
    )
    if not m:
        raise Http404()
    if m.out_of_service or Load.objects.filter(machine=m, ended_at=None).exists():
        raise ValidationError(
            f"{m.label} is unavailable. Refresh and choose an idle machine."
        )
    return m


def end_load(branch, load, staff, at):
    load.ended_at = at
    load.ended_by = staff
    load.save(update_fields=["ended_at", "ended_by"])
    minutes = max(0, int((at - load.started_at).total_seconds() // 60))
    payload = {
        "load_id": str(load.id),
        "machine": load.machine.label,
        "duration_minutes": minutes,
        "description": f"{load.machine.label} · Unloaded after {minutes} min",
    }
    if load.job_id:
        payload.update(job_id=str(load.job_id), number=load.job.number)
    append_event(branch, "load_ended", payload, at, staff)


def end_job_loads(branch, job, staff, at):
    for load in (
        Load.objects.select_for_update(of=("self",))
        .filter(branch=branch, job=job, ended_at=None)
        .select_related("machine", "job")
    ):
        end_load(branch, load, staff, at)


@transaction.atomic
@recorded_action
def start_for_job(branch, number, expected, target_id, machine_id, staff=None):
    branch, job = lock_job(branch, number, expected)
    if branch.simple_mode or job.paper_ref:
        raise ValidationError("Simple-mode and paper jobs do not use machine loads.")
    target = JobStage.objects.filter(
        pk=target_id, archived_at=None, ask_for_machine=True
    ).first()
    if not target:
        raise Http404()
    nxt = next_stage(job, branch)
    if target.pk != job.status_id and (not nxt or nxt.pk != target.pk):
        raise ValidationError(
            "Start a machine only for the current stage or the next stage from this job board."
        )
    m = active_machine(branch, machine_id)
    if target.machine_category_id and target.machine_category_id != m.category_id:
        raise ValidationError("Choose a machine in the stage’s category.")
    at = timezone.now()
    previous = job.status
    if target.pk != job.status_id:
        end_job_loads(branch, job, staff, at)
    load = Load.objects.create(
        shop_id=branch.shop_id,
        branch=branch,
        machine=m,
        job=job,
        stage=target,
        started_at=at,
        started_by=staff,
    )
    append_event(
        branch,
        "load_started",
        {
            "job_id": str(job.id),
            "number": job.number,
            "load_id": str(load.id),
            "machine": m.label,
            "stage": target.name,
            "description": f"Loaded {m.label} · {target.name}",
        },
        at,
        staff,
    )
    if target.pk != job.status_id:
        set_stage(job, target, at, staff)
        append_event(
            branch,
            "stage_changed",
            {
                "job_id": str(job.id),
                "number": job.number,
                "from": previous.name,
                "to": target.name,
                "cause": f"in {m.label}",
            },
            at,
            staff,
        )
    from supplies.services import deduct_load

    deduct_load(branch, load, staff, at)
    return load


@transaction.atomic
@recorded_action
def self_service(branch, machine_id, service_id, method, staff=None):
    branch = Branch.objects.select_for_update(of=("self",)).get(pk=branch.pk)
    if branch.simple_mode:
        raise Http404()
    m = active_machine(branch, machine_id)
    service = get_active(Service, service_id, archived_at=None, mode="load")
    if method not in ("cash", "gcash"):
        raise ValidationError("Collect Cash or GCash to start self-service.")
    amount = money(service.price)
    if amount < 0:
        raise ValidationError("Service price must be nonnegative.")
    at = timezone.now()
    load = Load.objects.create(
        shop_id=branch.shop_id,
        branch=branch,
        machine=m,
        self_service=True,
        amount=amount,
        pay_method=method,
        started_at=at,
        started_by=staff,
    )
    append_event(
        branch,
        "self_service_started",
        {
            "load_id": str(load.id),
            "machine": m.label,
            "service": service.name,
            "amount": str(amount),
            "method": method,
            "description": f"Self-service {m.label} · {service.name} · ₱{amount} · {method}",
        },
        at,
        staff,
    )
    from supplies.services import deduct_load

    deduct_load(branch, load, staff, at)
    return load


@transaction.atomic
@recorded_action
def unload(branch, machine_id, expected_load, staff=None):
    branch = Branch.objects.select_for_update(of=("self",)).get(pk=branch.pk)
    if branch.simple_mode:
        raise Http404()
    m = (
        Machine.objects.select_for_update(of=("self",))
        .filter(branch=branch, pk=machine_id, archived_at=None)
        .first()
    )
    if not m:
        raise Http404()
    load = (
        Load.objects.select_for_update(of=("self",))
        .filter(branch=branch, machine=m, ended_at=None)
        .select_related("machine", "job__status")
        .first()
    )
    if not load or str(load.id) != str(expected_load):
        raise ValidationError(
            "This load has already changed. Refreshed to the current machine state."
        )
    if load.job_id:
        require_job_operating_hours(branch)
    at = timezone.now()
    end_load(branch, load, staff, at)
    job = load.job
    if (
        job
        and not job.claimed_at
        and job.status_id == load.stage_id
        and job.status.move_on_when_unloaded
        and not Load.objects.filter(branch=branch, job=job, ended_at=None).exists()
    ):
        target = next_stage(job, branch)
        if target and not target.ask_for_machine:
            previous = job.status
            set_stage(job, target, at, staff)
            append_event(
                branch,
                "stage_changed",
                {
                    "job_id": str(job.id),
                    "number": job.number,
                    "from": previous.name,
                    "to": target.name,
                    "cause": f"last load unloaded from {m.label}",
                },
                at,
                staff,
            )
    return load
