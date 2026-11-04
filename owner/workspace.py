from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count, Sum
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from catalog.models import SupplyType
from core.models import Branch, JobStage, Machine, Settings
from jobs.models import Job
from machines.models import Load
from people.models import Device, Shift, Staff
from people.services import audit
from supplies.models import StockCount, StockEntry, SupplyRequest

from .admin_forms import EDITORS, OperationsForm, editor_form
from .views import owner, scoped_branch


def scope(request, single=False):
    owner(request)
    branches = list(Branch.objects.order_by("number"))
    selected = request.GET.get("branch", "all")
    if selected == "all" and not single:
        chosen = branches
        branch = None
    else:
        branch = (
            scoped_branch(selected)
            if selected != "all"
            else (branches[0] if branches else None)
        )
        chosen = [branch] if branch else []
    return {"branches": branches, "selected_branch": branch, "chosen": chosen}


@require_POST
def theme(request):
    owner(request)
    target = request.POST.get("next", "")
    # Keep the return destination inside this authenticated workspace.
    response = redirect(
        target
        if target.startswith("/owner/") and "\\" not in target
        else "owner_dashboard"
    )
    response.set_cookie(
        "app_theme",
        "dark" if request.POST.get("theme") == "dark" else "light",
        max_age=31536000,
        samesite="Lax",
        httponly=True,
    )
    return response


def collections(branches, day):
    # Same collection-time accounting as staff History; never count an unpaid job as sales.
    from events.models import Event

    amounts = {"cash": Decimal("0"), "gcash": Decimal("0")}
    for event in Event.objects.filter(
        branch__in=branches,
        occurred_at__date=day,
        type__in=["payment_recorded", "self_service_started"],
    ):
        method = event.payload.get("method")
        if method in amounts:
            amounts[method] += Decimal(event.payload["amount"])
    return {**amounts, "total": sum(amounts.values())}


@require_GET
@never_cache
def dashboard(request):
    ctx = scope(request)
    branches, day = ctx["chosen"], timezone.localdate()
    jobs = Job.objects.filter(branch__in=branches)
    ready = jobs.filter(claimed_at=None, status__is_last=True)
    machines = Machine.objects.filter(
        branch__in=branches, archived_at=None, category__archived_at=None
    )
    counts = dict(
        Load.objects.filter(branch__in=branches, started_at__date=day)
        .values_list("machine_id")
        .annotate(n=Count("id"))
    )
    maximum = max(counts.values(), default=1) or 1
    bars, alerts, stock_counts = [], [], []
    supplies = list(SupplyType.objects.filter(archived_at=None))
    balances = {
        (r["branch_id"], r["supply_type_id"]): r["total"]
        for r in StockEntry.objects.filter(branch__in=branches)
        .values("branch_id", "supply_type_id")
        .annotate(total=Sum("qty"))
    }
    for b in branches:
        bars.append(
            {
                "branch": b,
                "machines": [
                    {
                        "machine": m,
                        "count": counts.get(m.id, 0),
                        "width": counts.get(m.id, 0) * 100 / maximum,
                    }
                    for m in machines.filter(branch=b)
                    .select_related("category")
                    .order_by("category__sort_order", "label")
                ],
            }
        )
        for supply in supplies:
            amount = balances.get((b.id, supply.id), Decimal("0"))
            if amount <= supply.low_level:
                alerts.append(
                    {
                        "kind": "crit",
                        "text": f"{supply.name} is low at {b.name}: {amount:g} {supply.unit} left.",
                    }
                )
        full = (
            StockCount.objects.filter(branch=b, partial=False).order_by("-at").first()
        )
        age = (day - timezone.localdate(full.at)).days if full else None
        stock_counts.append(
            {
                "branch": b,
                "full": full,
                "kind": "good"
                if age is not None and age <= 1
                else "warn"
                if age == 2
                else "crit",
            }
        )
        latest = StockCount.objects.filter(branch=b).order_by("-at").first()
        if latest:
            for line in latest.lines.exclude(variance=0).select_related("supply_type"):
                alerts.append(
                    {
                        "kind": "warn",
                        "text": f"Count mismatch at {b.name}: {line.supply_type.name} {line.variance:+g} vs expected ({timezone.localtime(latest.at):%d %b, %H:%M}).",
                    }
                )
    for j in ready.filter(
        ready_at__lt=timezone.now() - timedelta(days=2)
    ).select_related("branch"):
        alerts.append(
            {
                "kind": "warn",
                "text": f"Job #{j.number} at {j.branch.name} has been ready for over two days.",
            }
        )
    ctx.update(
        sales=collections(branches, day),
        today=day,
        loads_today=sum(counts.values()),
        running=Load.objects.filter(branch__in=branches, ended_at=None).count(),
        machine_count=machines.count(),
        received=jobs.filter(received_at__date=day).count(),
        kilos=jobs.filter(received_at__date=day).aggregate(n=Sum("kg"))["n"] or 0,
        ready=ready.count(),
        due=ready.filter(paid_at=None).aggregate(n=Sum("total"))["n"] or 0,
        bars=bars,
        alerts=alerts,
        stock_counts=stock_counts,
        requests=SupplyRequest.objects.filter(
            branch__in=branches, status="open"
        ).select_related("branch"),
        devices=Device.objects.filter(branch__in=branches, revoked_at=None)
        .select_related("branch")
        .order_by("branch__number", "name"),
    )
    return render(request, "owner/dashboard.html", ctx)


@require_GET
@never_cache
def live(request):
    from jobs.board import columns
    from machines.views import tiles

    ctx = scope(request, single=True)
    b = ctx["selected_branch"]
    ts = tiles(b) if b and not b.simple_mode else []
    jobs = Job.objects.filter(branch=b, claimed_at=None) if b else Job.objects.none()
    ctx.update(
        tiles=ts,
        columns=columns(b) if b else [],
        running=sum(bool(t["load"]) for t in ts),
        check=sum(t["flag"] for t in ts),
        progress=jobs.exclude(status__is_last=True).count(),
        ready=jobs.filter(status__is_last=True).count(),
        refreshed_at=timezone.now(),
    )
    return render(request, "owner/live.html", ctx)


@require_GET
@never_cache
def counts(request, branch_id):
    owner(request)
    b = get_object_or_404(Branch, pk=branch_id)
    from django.core.paginator import Paginator

    rows = (
        StockCount.objects.filter(branch=b)
        .select_related("by", "device")
        .prefetch_related("lines__supply_type")
        .order_by("-at")
    )
    return render(
        request,
        "owner/counts.html",
        {
            "count_branch": b,
            "counts": Paginator(rows, 20).get_page(request.GET.get("page")),
        },
    )


@require_GET
@never_cache
def staff(request):
    from .views import dashboard_context

    ctx = {**dashboard_context(request), **scope(request)}
    people = list(
        Staff.objects.filter(branch__in=ctx["chosen"])
        .select_related("branch")
        .order_by("branch__number", "name")
    )
    for person in people:
        person.current_shift = Shift.objects.filter(
            staff=person, ended_at=None, ends_at__gt=timezone.now()
        ).first()
    ctx["people"] = people
    return render(request, "owner/staff.html", ctx)


def sections(kinds):
    result = []
    for kind in kinds:
        model, fields, title = EDITORS[kind]
        rows = []
        relations = [
            f.name for f in model._meta.fields if f.is_relation and f.name != "shop"
        ]
        for obj in model.objects.select_related(*relations).all():
            values = []
            for field in fields:
                val = getattr(obj, field)
                if field == "mode":
                    val = obj.get_mode_display()
                elif isinstance(val, bool):
                    val = "Yes" if val else "No"
                elif hasattr(val, "name"):
                    val = val.name
                values.append(val if val is not None else "—")
            rows.append(
                {
                    "object": obj,
                    "values": values,
                    "archived": bool(getattr(obj, "archived_at", None))
                    or getattr(obj, "active", True) is False,
                }
            )
        form = editor_form(kind)()
        result.append(
            {
                "kind": kind,
                "title": title,
                "headers": [f.label for f in form.fields.values()],
                "rows": rows,
            }
        )
    return result


@require_http_methods(["GET", "POST"])
@never_cache
def settings_page(request):
    from .forms import PolicyForm, ShopBrandingForm

    own = owner(request)
    config = Settings.objects.get(shop_id=own.shop_id)
    branding = (
        ShopBrandingForm(request.POST or None, request.FILES or None, instance=own.shop)
        if request.method == "POST"
        else ShopBrandingForm(instance=own.shop)
    )
    # Retains the existing branding POST contract.
    if request.method == "POST" and branding.is_valid():
        branding.save()
        messages.success(request, "Shop branding saved.")
        return redirect("owner_shop_settings")
    return render(
        request,
        "owner/settings.html",
        {
            "branding_form": branding,
            "operations_form": OperationsForm(instance=config),
            "policy_form": PolicyForm(
                initial={
                    "pin_enabled": config.pin_enabled,
                    "pin_actions": config.pin_actions,
                }
            ),
            "branches": Branch.objects.order_by("number"),
            "sections": sections(
                [
                    "stage",
                    "service",
                    "fee",
                    "addon",
                    "recipe",
                    "supply",
                    "piece",
                    "size",
                ]
            ),
        },
        status=422 if branding.errors else 200,
    )


@require_POST
@transaction.atomic
def operations(request):
    own = owner(request)
    list(Branch.objects.select_for_update().order_by("pk"))
    config = Settings.objects.select_for_update().get(shop_id=own.shop_id)
    form = OperationsForm(request.POST, instance=config)
    if form.is_valid():
        config.version += 1
        form.save()
        for b in Branch.objects.all():
            audit(
                b, "settings_updated", "Operational settings updated", owner=own.email
            )
        messages.success(request, "Operational settings saved.")
        return redirect("owner_shop_settings")
    return render(
        request,
        "owner/editor.html",
        {
            "form": form,
            "heading": "Operational settings",
            "back": "owner_shop_settings",
        },
        status=422,
    )


@require_POST
@transaction.atomic
def branch_mode(request, branch_id):
    own = owner(request)
    b = get_object_or_404(Branch.objects.select_for_update(), pk=branch_id)
    desired = request.POST.get("simple_mode") == "1"
    if desired and Load.objects.filter(branch=b, ended_at=None).exists():
        messages.error(
            request, "Unload running machines before switching to simple mode."
        )
    else:
        b.simple_mode = desired
        b.save(update_fields=["simple_mode"])
        audit(b, "branch_mode_updated", "Branch workflow mode updated", owner=own.email)
        messages.success(request, "Branch workflow saved.")
    return redirect("owner_shop_settings")


@require_GET
@never_cache
def machines(request):
    ctx = scope(request)
    ctx["sections"] = sections(["category"])
    ctx["machine_groups"] = [
        {
            "branch": b,
            "machines": Machine.objects.filter(branch=b)
            .select_related("category")
            .order_by("category__sort_order", "label"),
        }
        for b in ctx["chosen"]
    ]
    return render(request, "owner/machines.html", ctx)


def archive(obj, kind):
    if kind == "stage":
        if obj.is_first or obj.is_last:
            raise ValidationError("Keep the first and Ready stages.")
        if (
            Job.objects.filter(status=obj, claimed_at=None).exists()
            or Load.objects.filter(stage=obj, ended_at=None).exists()
        ):
            raise ValidationError(
                "Move active jobs and unload machines before removing this stage."
            )
    if kind == "category" and (
        Machine.objects.filter(category=obj, archived_at=None).exists()
        or JobStage.objects.filter(machine_category=obj, archived_at=None).exists()
    ):
        raise ValidationError(
            "Reassign machines and stages before removing their category."
        )
    if kind == "machine" and Load.objects.filter(machine=obj, ended_at=None).exists():
        raise ValidationError("Unload this machine before removing it.")
    if kind == "recipe":
        obj.delete()
    elif kind == "size":
        obj.active = not obj.active
        obj.save(update_fields=["active"])
    else:
        obj.archived_at = None if obj.archived_at else timezone.now()
        # Core nullable fields predate these forms and do not set blank=True.
        excluded = [
            f.name
            for f in obj._meta.fields
            if f.null and not f.blank and getattr(obj, f.attname) is None
        ]
        obj.full_clean(exclude=excluded)
        obj.save(update_fields=["archived_at"])


def save_stage(target):
    remaining = list(
        JobStage.objects.filter(archived_at=None)
        .exclude(pk=target.pk)
        .order_by("sort_order", "id")
    )
    # Insert before Ready when restoring an old stage whose old order is now occupied.
    index = (
        next(
            (
                i
                for i, stage in enumerate(remaining)
                if stage.is_last or stage.sort_order >= target.sort_order
            ),
            len(remaining),
        )
        if not target.is_last
        else len(remaining)
    )
    remaining.insert(index, target)
    for position, stage in enumerate(remaining):
        stage.sort_order = position
        stage.save()


@require_http_methods(["GET", "POST"])
@never_cache
def edit(request, kind, record_id=None):
    own = owner(request)
    if kind not in EDITORS:
        raise Http404()
    model, _, title = EDITORS[kind]
    back = (
        "owner_machines" if kind in ("machine", "category") else "owner_shop_settings"
    )
    obj = (
        get_object_or_404(model, pk=record_id)
        if record_id
        else model(shop_id=own.shop_id)
    )
    try:
        source = (
            get_object_or_404(SupplyRequest, pk=request.GET["request"], status="open")
            if kind == "supply" and request.GET.get("request")
            else None
        )
    except (ValidationError, ValueError):
        raise Http404()
    initial = {"name": source.name} if source else {}
    if kind == "machine" and request.GET.get("branch"):
        initial["branch"] = scoped_branch(request.GET["branch"])
    if kind == "stage" and not record_id:
        last = JobStage.objects.filter(is_last=True, archived_at=None).first()
        initial["sort_order"] = last.sort_order if last else 1
    form = editor_form(kind)(
        request.POST if request.method == "POST" else None,
        instance=obj,
        initial=initial,
    )
    if request.method == "POST":
        try:
            with transaction.atomic():
                # Same branch lock order as counter operations, preventing changes during load starts.
                branches = list(Branch.objects.select_for_update().order_by("pk"))
                config = Settings.objects.select_for_update().get(shop_id=own.shop_id)
                if source:
                    source = get_object_or_404(
                        SupplyRequest.objects.select_for_update(),
                        pk=source.pk,
                        status="open",
                    )
                if record_id:
                    obj = get_object_or_404(
                        model.objects.select_for_update(), pk=record_id
                    )
                    form = editor_form(kind)(request.POST, instance=obj)
                if request.POST.get("action") == "archive" and record_id:
                    archive(obj, kind)
                    if kind == "stage" and not obj.archived_at:
                        save_stage(obj)
                elif form.is_valid():
                    if kind == "stage":
                        save_stage(form.save(commit=False))
                    else:
                        form.save()
                    if source:
                        source.status = "fulfilled"
                        source.save(update_fields=["status"])
                else:
                    return render(
                        request,
                        "owner/editor.html",
                        {"form": form, "heading": title, "back": back},
                        status=422,
                    )
                config.version += 1
                config.save(update_fields=["version"])
                for b in branches:
                    audit(
                        b, "configuration_updated", f"{title} updated", owner=own.email
                    )
            messages.success(request, f"{title} saved.")
            return redirect(back)
        except (ValidationError, IntegrityError) as e:
            form.add_error(
                None,
                " ".join(e.messages)
                if isinstance(e, ValidationError)
                else "A record with these values already exists.",
            )
    return render(
        request,
        "owner/editor.html",
        {
            "form": form,
            "heading": ("Edit " if record_id else "Add · ") + title,
            "back": back,
        },
        status=422 if form.errors else 200,
    )
