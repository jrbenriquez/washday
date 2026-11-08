from events.feedback import success as reversible_success
from people.guards import pin_guard
from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from django.core.exceptions import ValidationError
from django.contrib import messages
from django.utils import timezone
from .views import require_branch
from .models import Job
from .transitions import stages, next_stage, advance, override, claim, StaleAction


def columns(branch):
    visible = stages(branch)
    cols = [{"stage": s, "cards": []} for s in visible]
    for job in (
        Job.objects.filter(branch=branch, claimed_at=None)
        .select_related("status", "customer")
        .order_by("received_at")
    ):
        col = next(
            (
                c
                for c in reversed(cols)
                if c["stage"].sort_order <= job.status.sort_order
            ),
            cols[0],
        )
        job.next_stage = next(
            (s for s in visible if s.sort_order > job.status.sort_order), None
        )
        job.current_machine_start = bool(
            not branch.simple_mode and not job.paper_ref and job.status.ask_for_machine
        )
        job.next_machine_start = bool(
            not branch.simple_mode
            and not job.paper_ref
            and job.next_stage
            and job.next_stage.ask_for_machine
        )
        job.hidden_stage = col["stage"].id != job.status_id
        job.overdue = bool(
            job.ready_at and timezone.now() - job.ready_at > timedelta(days=2)
        )
        job.age_minutes = int((timezone.now() - job.received_at).total_seconds() // 60)
        col["cards"].append(job)
    return cols


def board_context(request):
    branch = require_branch(request)
    return {
        "columns": columns(branch),
        "claimed_today": Job.objects.filter(
            branch=branch, claimed_at__date=timezone.localdate()
        ).count(),
        "stages": stages(branch),
    }


@require_GET
def board(request):
    if request.GET.get("view") in ("list", "history"):
        from .history import listing

        return listing(request)
    return render(request, "jobs/board.html", board_context(request))


@require_http_methods(["GET", "POST"])
def edit(request, number):
    branch = require_branch(request)
    job = get_object_or_404(
        Job.objects.select_related("status"), branch=branch, number=number
    )
    if request.method == "POST":
        gate = pin_guard(request, "override")
        if gate is not None:
            return gate
        try:
            override(
                branch,
                number,
                request.POST.get("expected"),
                request.POST.get("target"),
                request.POST.get("reason", ""),
                request.staff,
            )
            reversible_success(request, f"Job #{number}: stage corrected.")
            return redirect("board")
        except StaleAction as e:
            messages.error(request, " ".join(e.messages))
            return redirect("board")
        except ValidationError as e:
            return render(
                request,
                "jobs/edit.html",
                {"job": job, "stages": stages(branch), "error": " ".join(e.messages)},
                status=422,
            )
    return render(request, "jobs/edit.html", {"job": job, "stages": stages(branch)})


@require_POST
def move(request, number):
    branch = require_branch(request)
    job = get_object_or_404(
        Job.objects.select_related("status"), branch=branch, number=number
    )
    target = next_stage(job, branch)
    if (
        str(job.status_id) == str(request.POST.get("expected"))
        and not job.claimed_at
        and not branch.simple_mode
        and not job.paper_ref
        and target
        and target.ask_for_machine
        and not request.POST.get("skip_reason", "").strip()
    ):
        from django.urls import reverse

        return redirect(
            reverse("machine_picker", args=[number])
            + "?target="
            + str(target.id)
            + "&expected="
            + str(job.status_id)
        )
    try:
        job = advance(
            branch,
            number,
            request.POST.get("expected"),
            request.staff,
            request.POST.get("skip_reason", ""),
            request.POST.get("paper_ready") == "1",
        )
        reversible_success(request, f"Job #{number} moved to {job.status.name}.")
    except StaleAction as e:
        messages.error(request, " ".join(e.messages))
    except ValidationError as e:
        job = get_object_or_404(
            Job.objects.select_related("status"), branch=branch, number=number
        )
        return render(
            request,
            "jobs/skip.html",
            {"job": job, "error": " ".join(e.messages)},
            status=422,
        )
    return redirect("board")


@require_http_methods(["GET", "POST"])
def release(request, number):
    branch = require_branch(request)
    job = get_object_or_404(
        Job.objects.select_related("status"), branch=branch, number=number
    )
    if request.method == "POST":
        gate = pin_guard(request, "claim", *(["payment"] if not job.paid_at else []))
        if gate is not None:
            return gate
        try:
            claim(
                branch,
                number,
                request.POST.get("expected"),
                request.POST,
                request.staff,
            )
            reversible_success(request, f"Job #{number} claimed.")
            return redirect("stub", number=number)
        except StaleAction as e:
            messages.error(request, " ".join(e.messages))
            return redirect("board")
        except ValidationError as e:
            return render(
                request,
                "jobs/claim.html",
                {"job": job, "error": " ".join(e.messages), "data": request.POST},
                status=422,
            )
    return render(request, "jobs/claim.html", {"job": job})
