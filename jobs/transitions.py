from django.db import transaction
from django.db.models import Q
from django.core.exceptions import ValidationError
from django.http import Http404
from django.utils import timezone
from core.models import Branch, JobStage
from .models import Job
from .services import append_event, sheet_time


class StaleAction(ValidationError):
    pass


def stages(branch):
    q = JobStage.objects.filter(archived_at=None).order_by("sort_order")
    return (
        list(q.filter(Q(is_first=True) | Q(is_last=True) | Q(show_in_simple_mode=True)))
        if branch.simple_mode
        else list(q)
    )


def actual_name(job):
    return "Claimed" if job.claimed_at else job.status.name


def lock_job(branch, number, expected):
    branch = Branch.objects.select_for_update().get(pk=branch.pk)
    job = (
        Job.objects.select_for_update()
        .filter(branch=branch, number=number)
        .select_related("status")
        .first()
    )
    if not job:
        raise Http404()
    if job.claimed_at or str(job.status_id) != str(expected):
        raise StaleAction(
            f"Job #{job.number} is already in {actual_name(job)}. Refreshed to the current stage."
        )
    return branch, job


def next_stage(job, branch):
    return next(
        (s for s in stages(branch) if s.sort_order > job.status.sort_order), None
    )


def set_stage(job, target, at, staff=None):
    first_arrival = target.is_last and job.first_ready_at is None
    job.status = target
    job.ready_at = at if target.is_last else None
    if target.is_last and not job.first_ready_at:
        job.first_ready_at = at
    job.save(update_fields=["status", "ready_at", "first_ready_at"])
    if first_arrival:
        from supplies.services import deduct_packing

        deduct_packing(job.branch, job, staff, at)


@transaction.atomic
def advance(branch, number, expected, staff=None, skip_reason="", paper_ready=False):
    branch, job = lock_job(branch, number, expected)
    target = (
        JobStage.objects.filter(is_last=True, archived_at=None).get()
        if paper_ready and job.paper_ref
        else next_stage(job, branch)
    )
    if not target:
        raise ValidationError("This job is Ready. Use Claim to release it.")
    if (
        target.ask_for_machine
        and not branch.simple_mode
        and not job.paper_ref
        and not skip_reason.strip()
    ):
        raise ValidationError(
            "Choose a machine, or enter a reason for no machine recorded."
        )
    previous = job.status
    at = timezone.now()
    from machines.services import end_job_loads

    end_job_loads(branch, job, staff, at)
    set_stage(job, target, at, staff)
    payload = {
        "job_id": str(job.id),
        "number": job.number,
        "from": previous.name,
        "to": target.name,
        "reason": skip_reason.strip()
        if target.ask_for_machine and not branch.simple_mode and not job.paper_ref
        else "",
        "no_machine": bool(
            target.ask_for_machine and not branch.simple_mode and not job.paper_ref
        ),
        "from_paper": bool(job.paper_ref),
    }
    append_event(branch, "stage_changed", payload, at, staff)
    return job


@transaction.atomic
def override(branch, number, expected, target_id, reason="", staff=None):
    branch, job = lock_job(branch, number, expected)
    target = next((s for s in stages(branch) if str(s.id) == str(target_id)), None)
    if not target:
        raise Http404()
    previous = job.status
    at = timezone.now()
    set_stage(job, target, at, staff)
    append_event(
        branch,
        "stage_overridden",
        {
            "job_id": str(job.id),
            "number": job.number,
            "from": previous.name,
            "to": target.name,
            "reason": reason,
            "description": f"Stage changed to {target.name}, manual override from {previous.name}",
        },
        at,
        staff,
    )
    return job


@transaction.atomic
def claim(branch, number, expected, data, staff=None):
    branch, job = lock_job(branch, number, expected)
    if not job.status.is_last:
        raise ValidationError("Only a Ready job can be claimed.")
    at = timezone.now()
    paper = str(data.get("paper_release", "")) == "1"
    claimed = (
        sheet_time(data.get("release_date"), data.get("release_time")) if paper else at
    )
    if claimed < job.received_at:
        raise ValidationError("Release cannot precede receipt.")
    if not job.paid_at:
        method = data.get("pay_method", "")
        if method not in ("cash", "gcash"):
            raise ValidationError("Collect Cash or GCash before releasing this job.")
        paid = (
            sheet_time(data.get("release_date"), data.get("paid_time")) if paper else at
        )
        if paid < job.received_at or paid > claimed:
            raise ValidationError("Payment must be between receipt and release.")
        ref = data.get("pay_ref", "").strip() if method == "gcash" else ""
        if len(ref) > 120:
            raise ValidationError("GCash reference is too long.")
        job.pay_method = method
        job.paid_at = paid
        job.pay_ref = ref
        job.paid_amount = job.total
        append_event(
            branch,
            "payment_recorded",
            {
                "job_id": str(job.id),
                "number": job.number,
                "amount": str(job.total),
                "method": method,
                "reference": ref,
                "context": "at claim",
                "from_paper": paper,
            },
            paid,
            staff,
        )
    elif job.paid_at > claimed:
        raise ValidationError("Release cannot precede the recorded payment.")
    job.claimed_at = claimed
    job.save(
        update_fields=["claimed_at", "pay_method", "paid_at", "pay_ref", "paid_amount"]
    )
    append_event(
        branch,
        "job_claimed",
        {
            "job_id": str(job.id),
            "number": job.number,
            "from_paper": paper,
            "claimed_at": claimed.isoformat(),
        },
        claimed,
        staff,
    )
    return job
