from datetime import date, timedelta
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_GET
from django.utils import timezone
from events.models import Event
from .models import Job
from .views import require_branch


def day_value(raw):
    try:
        return date.fromisoformat(raw) if raw else timezone.localdate()
    except (ValueError, TypeError):
        raise ValidationError("Choose a valid calendar date.")


def day_of(at):
    return timezone.localdate(at)


def project(branch):
    # Membership, state changes and collections come from Events, including released jobs.
    # Join stable job metadata for events created before customer snapshot fields were added.
    jobs = {
        str(j.id): j
        for j in Job.objects.filter(branch=branch).select_related(
            "customer", "created_by", "status"
        )
    }
    rows = {}
    events = list(
        Event.objects.filter(branch=branch)
        .select_related("actor_staff", "device")
        .order_by("seq")
    )
    for event in events:
        p = event.payload
        jid = p.get("job_id")
        j = jobs.get(jid)
        if event.type == "job_created" and j:
            rows[jid] = {
                "job": j,
                "number": p["number"],
                "customer": p.get(
                    "customer_name", j.customer.name if j.customer else "Walk-in"
                ),
                "phone": p.get(
                    "customer_phone", j.customer.phone if j.customer else ""
                ),
                "notes": p.get("notes", j.notes),
                "kg": p.get("kg", str(j.kg)),
                "pieces": p.get("pieces", j.pieces),
                "service": p.get(
                    "service_name",
                    next(
                        (l["label"] for l in p.get("lines", []) if l["kind"] == "base"),
                        "Pieces only",
                    ),
                ),
                "lines": p.get("lines", []),
                "total": p["total"],
                "received_at": event.occurred_at,
                "paid_at": None,
                "claimed_at": None,
                "method": "",
                "reference": "",
                "paid_amount": Decimal("0"),
                "status": "Received",
                "paper_ref": p.get("paper_ref", ""),
                "from_paper": p.get("from_paper", False),
                "events": [],
            }
        row = rows.get(jid)
        if row:
            row["events"].append(event)
            if event.type in ("stage_changed", "stage_overridden"):
                row["status"] = p.get("to", row["status"])
            if event.type == "payment_recorded":
                row.update(
                    paid_at=event.occurred_at,
                    method=p["method"],
                    reference=p.get("reference", ""),
                    paid_amount=Decimal(p["amount"]),
                )
            if event.type == "job_claimed":
                row.update(claimed_at=event.occurred_at, status="Claimed")
            if event.type == "action_undone" and p.get("job_state"):
                from django.utils.dateparse import parse_datetime

                state = p["job_state"]
                row.update(**state)
                for field in ("paid_at", "claimed_at"):
                    row[field] = parse_datetime(state[field]) if state[field] else None
                row["paid_amount"] = Decimal(state["paid_amount"])
    return list(rows.values()), events


def annotate(event):
    p = event.payload
    event.kind = {
        "payment_recorded": "paid",
        "job_claimed": "claimed",
        "stage_overridden": "override",
        "stage_changed": "stage",
    }.get(event.type, "received")
    event.job_number = p.get("number")
    event.actor = (
        event.actor_staff.name
        if event.actor_staff
        else event.device.name
        if event.device
        else p.get("owner", "Development device")
    )
    if event.type == "job_created":
        details = f"{p.get('kg', '0.0')} kg · ₱{p.get('total', '0.00')}"
        event.description = "Received · " + details
        if p.get("from_paper"):
            event.description += f" · Received on paper as {p.get('paper_ref')}, entered by {p.get('entered_by', 'Staff')} at {p.get('entered_at')}"
    elif event.type == "payment_reversed":
        event.kind = "override"
        event.description = f"Payment reversed · ₱{p['amount']} · {p['method']}"
    elif event.type == "payment_recorded":
        event.description = (
            f"Paid · ₱{p['amount']} · {p['method']} · {p.get('context', '')}"
            + (f" · Reference {p['reference']}" if p.get("reference") else "")
        )
    elif event.type == "job_claimed":
        event.description = "Released" + (" on paper" if p.get("from_paper") else "")
    elif event.type == "stage_overridden":
        event.description = p.get(
            "description",
            f"Stage changed to {p.get('to')}, manual override from {p.get('from')}",
        ) + (f" · {p['reason']}" if p.get("reason") else "")
    elif event.type == "stage_changed":
        event.description = (
            f"Stage changed to {p.get('to')}"
            + (f" · no machine recorded · {p['reason']}" if p.get("no_machine") else "")
            + (f" · {p['cause']}" if p.get("cause") else "")
        )
    else:
        event.description = p.get(
            "description", event.type.replace("_", " ").capitalize()
        )
    return event


@require_GET
def listing(request):
    branch = require_branch(request)
    try:
        day = day_value(request.GET.get("date"))
    except ValidationError as e:
        return render(
            request,
            "jobs/list.html",
            {"error": " ".join(e.messages), "view": request.GET.get("view", "list")},
            status=422,
        )
    rows, events = project(branch)
    query = request.GET.get("q", "").strip().casefold()
    view = request.GET.get("view", "list")
    matches = []
    for r in rows:
        text = " ".join(
            [
                str(r["number"]),
                r["paper_ref"],
                r["customer"],
                r["phone"],
                r["notes"],
                r["status"],
                r["method"],
            ]
        ).casefold()
        if query:
            if query in text:
                matches.append(r)
        elif any(
            at and day_of(at) == day
            for at in [r["received_at"], r["paid_at"], r["claimed_at"]]
        ):
            matches.append(r)
    matches.sort(key=lambda r: r["received_at"], reverse=True)
    day_events = [e for e in events if day_of(e.occurred_at) == day]
    if query:
        wanted = {str(r["job"].id) for r in matches}
        display_events = [e for e in events if e.payload.get("job_id") in wanted]
    else:
        display_events = day_events
    summary = {
        "received": sum(e.type == "job_created" for e in day_events),
        "released": sum(e.type == "job_claimed" for e in day_events)
        - sum(e.type == "claim_reversed" for e in day_events),
        "cash": Decimal("0.00"),
        "gcash": Decimal("0.00"),
    }
    for e in day_events:
        if e.type in ("payment_recorded", "self_service_started", "payment_reversed"):
            method = e.payload.get("method")
            if method in ("cash", "gcash"):
                summary[method] += Decimal(e.payload["amount"]) * (
                    -1 if e.type == "payment_reversed" else 1
                )
    summary["total"] = summary["cash"] + summary["gcash"]
    return render(
        request,
        "jobs/list.html",
        {
            "view": view,
            "day": day,
            "yesterday": timezone.localdate() - timedelta(days=1),
            "today": timezone.localdate(),
            "query": request.GET.get("q", ""),
            "rows": matches,
            "events": [
                annotate(e)
                for e in sorted(
                    display_events, key=lambda e: (e.occurred_at, e.seq), reverse=True
                )
            ],
            "summary": summary,
        },
    )


@require_GET
def timeline(request, number):
    branch = require_branch(request)
    job = get_object_or_404(Job, branch=branch, number=number)
    rows, events = project(branch)
    row = next((r for r in rows if r["job"].id == job.id), None)
    events = [annotate(e) for e in events if e.payload.get("job_id") == str(job.id)]
    return render(
        request,
        "jobs/timeline.html",
        {
            "job": job,
            "row": row,
            "events": sorted(events, key=lambda e: (e.occurred_at, e.seq)),
            "lines": job.lines.all(),
        },
    )
