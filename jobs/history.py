from datetime import date, datetime, time, timedelta
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import (
    Case,
    CharField,
    Count,
    DecimalField,
    F,
    IntegerField,
    Q,
    Sum,
    Value,
    When,
    Window,
)
from django.db.models.fields.json import KT
from django.db.models.functions import Cast, Coalesce, Concat, Replace, RowNumber
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


def project(branch, jobs=None):
    # Membership, state changes and collections come from Events, including released jobs.
    # Join stable job metadata for events created before customer snapshot fields were added.
    if jobs is None:
        jobs = Job.objects.filter(branch=branch).select_related(
            "customer", "created_by", "status"
        )
    jobs = {str(j.id): j for j in jobs}
    rows = {}
    events = list(
        Event.objects.filter(branch=branch, payload__job_id__in=list(jobs))
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
        else event.device.name if event.device else p.get("owner", "Development device")
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


PAGE_SIZE = 50


def day_bounds(day):
    start = timezone.make_aware(datetime.combine(day, time.min))
    end = timezone.make_aware(datetime.combine(day + timedelta(days=1), time.min))
    return start, end


def matching_jobs(branch, day, query):
    jobs = Job.objects.filter(branch=branch)
    if not query:
        start, end = day_bounds(day)
        return jobs.filter(
            Q(received_at__gte=start, received_at__lt=end)
            | Q(paid_at__gte=start, paid_at__lt=end)
            | Q(claimed_at__gte=start, claimed_at__lt=end)
        )

    # Search snapshots in sets, without a correlated event scan for every job.
    events = Event.objects.filter(branch=branch)
    created = events.filter(type="job_created")

    def numbers(queryset):
        return (
            queryset.order_by()
            .annotate(job_number=Cast(KT("payload__number"), IntegerField()))
            .values("job_number")
        )

    def latest(queryset):
        ids = (
            queryset.annotate(
                position=Window(
                    RowNumber(),
                    partition_by=[KT("payload__job_id")],
                    order_by=F("seq").desc(),
                )
            )
            .filter(position=1)
            .values("pk")
        )
        # Keep text matching outside the window query: an old matching state
        # must not hide a newer nonmatching state (especially after Undo).
        return events.filter(pk__in=ids)

    state_events = events.filter(
        Q(type__in=["stage_changed", "stage_overridden", "job_claimed"])
        | Q(type="action_undone", payload__job_state__status__isnull=False)
    )
    status = latest(state_events).alias(
        label=Case(
            When(type="job_claimed", then=Value("Claimed")),
            When(type="action_undone", then=KT("payload__job_state__status")),
            default=KT("payload__to"),
            output_field=CharField(),
        )
    )
    payment = latest(
        events.filter(
            Q(type="payment_recorded")
            | Q(type="action_undone", payload__job_state__method__isnull=False)
        )
    ).alias(
        label=Case(
            When(type="action_undone", then=KT("payload__job_state__method")),
            default=KT("payload__method"),
            output_field=CharField(),
        )
    )
    snapshots = created.alias(
        text=Concat(
            Coalesce(KT("payload__customer_name"), Value(""), output_field=CharField()),
            Value(" "),
            Coalesce(
                KT("payload__customer_phone"), Value(""), output_field=CharField()
            ),
            Value(" "),
            Coalesce(KT("payload__notes"), Value(""), output_field=CharField()),
            output_field=CharField(),
        )
    ).filter(text__icontains=query)
    jobs = jobs.alias(
        number_text=Cast("number", CharField()),
        customer_label=Coalesce("customer__name", Value("Walk-in")),
    )
    matches = (
        Q(number_text__icontains=query)
        | Q(paper_ref__icontains=query)
        | Q(number__in=numbers(snapshots))
        | Q(number__in=numbers(status.filter(label__icontains=query)))
        | Q(number__in=numbers(payment.filter(label__icontains=query)))
    )
    if query.casefold() in "received":
        matches |= ~Q(number__in=numbers(state_events))
    # Older events predate customer/notes snapshots; retain their metadata fallback.
    for key, field in [
        ("customer_name", "customer_label"),
        ("customer_phone", "customer__phone"),
        ("notes", "notes"),
    ]:
        missing = created.filter(**{"payload__" + key + "__isnull": True})
        matches |= Q(number__in=numbers(missing)) & Q(**{field + "__icontains": query})
    return jobs.filter(number__in=numbers(created)).filter(matches)


def events_for_jobs(branch, jobs):
    # UUID storage differs between SQLite (hex) and PostgreSQL (hyphenated).
    keys = jobs.annotate(
        job_key=Replace(Cast("pk", CharField()), Value("-"), Value(""))
    )
    return (
        Event.objects.filter(branch=branch)
        .alias(
            job_key=Replace(
                KT("payload__job_id"), Value("-"), Value(""), output_field=CharField()
            )
        )
        .filter(job_key__in=keys.order_by().values("job_key"))
    )


def day_summary(events):
    money = DecimalField(max_digits=20, decimal_places=2)
    amount = Cast(KT("payload__amount"), money)
    signed = Case(
        When(type="payment_reversed", then=-amount), default=amount, output_field=money
    )
    collections = Q(
        type__in=["payment_recorded", "self_service_started", "payment_reversed"]
    )
    summary = events.aggregate(
        received=Count("pk", filter=Q(type="job_created")),
        claimed=Count("pk", filter=Q(type="job_claimed")),
        reversed=Count("pk", filter=Q(type="claim_reversed")),
        cash=Sum(
            signed, filter=collections & Q(payload__method="cash"), default=Decimal("0")
        ),
        gcash=Sum(
            signed,
            filter=collections & Q(payload__method="gcash"),
            default=Decimal("0"),
        ),
    )
    summary["released"] = summary.pop("claimed") - summary.pop("reversed")
    summary["total"] = summary["cash"] + summary["gcash"]
    return summary


@require_GET
def listing(request):
    branch = require_branch(request)
    try:
        day = day_value(request.GET.get("date"))
        start, end = day_bounds(day)
    except (ValidationError, OverflowError, ValueError) as e:
        error = (
            " ".join(e.messages)
            if isinstance(e, ValidationError)
            else "Choose a valid calendar date."
        )
        return render(
            request,
            "jobs/list.html",
            {"error": error, "view": request.GET.get("view", "list")},
            status=422,
        )
    query = request.GET.get("q", "").strip()
    view = request.GET.get("view", "list")
    day_events = Event.objects.filter(
        branch=branch, occurred_at__gte=start, occurred_at__lt=end
    )
    rows, display_events = [], []
    if view == "history":
        events = (
            events_for_jobs(branch, matching_jobs(branch, day, query))
            if query
            else day_events
        )
        page = Paginator(
            events.select_related("actor_staff", "device").order_by(
                "-occurred_at", "-seq"
            ),
            PAGE_SIZE,
        ).get_page(request.GET.get("page"))
        display_events = [annotate(e) for e in page]
        summary = day_summary(day_events)
    else:
        jobs = (
            matching_jobs(branch, day, query)
            .select_related("customer", "created_by", "status")
            .order_by("-received_at", "-number")
        )
        page = Paginator(jobs, PAGE_SIZE).get_page(request.GET.get("page"))
        rows, _ = project(branch, page.object_list)
        rows.sort(key=lambda r: (r["received_at"], r["number"]), reverse=True)
        summary = {}
    params = request.GET.copy()
    params.pop("page", None)
    return render(
        request,
        "jobs/list.html",
        {
            "view": view,
            "day": day,
            "yesterday": timezone.localdate() - timedelta(days=1),
            "today": timezone.localdate(),
            "query": request.GET.get("q", ""),
            "rows": rows,
            "events": display_events,
            "summary": summary,
            "page_obj": page,
            "page_query": params.urlencode(),
        },
    )


@require_GET
def timeline(request, number):
    branch = require_branch(request)
    job = get_object_or_404(
        Job.objects.select_related(
            "customer", "created_by", "created_device", "status"
        ),
        branch=branch,
        number=number,
    )
    rows, events = project(branch, [job])
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
