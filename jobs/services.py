from people.context import current_device, actor_name
import re
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, ROUND_CEILING
from django.db import transaction
from django.db.models import F
from django.core.exceptions import ValidationError
from django.http import Http404
from django.utils import timezone
from core.models import Branch, Settings, JobStage
from customers.models import Customer
from catalog.models import Service, AddOn, Fee, PieceVariant
from events.models import Event
from .models import Job, JobLine

CENT = Decimal("0.01")


def money(v):
    return Decimal(v).quantize(CENT, rounding=ROUND_HALF_UP)


def dec(value):
    try:
        d = Decimal(str(value))
        if not d.is_finite():
            raise ValueError()
        return d
    except (ValueError, InvalidOperation, TypeError):
        raise ValidationError("Enter a valid number.")


def get_active(model, key, **extra):
    try:
        obj = model.objects.filter(pk=key, **extra).first()
    except (ValidationError, ValueError):
        raise Http404()
    if not obj:
        raise Http404()
    return obj


def quote(data, branch):
    settings = Settings.objects.get(shop_id=branch.shop_id)
    kg = dec(data.get("kg", "0") or "0")
    if kg < 0 or kg > Decimal("99999.9") or kg.as_tuple().exponent < -1:
        raise ValidationError(
            "Weight must be nonnegative kg with at most one decimal place."
        )
    lines = []
    service = None
    pieces = []
    # Validate every supplied identifier even for a pieces-only job.
    if data.get("service"):
        service = get_active(Service, data["service"], archived_at=None)
    if kg > 0:
        if not service:
            raise ValidationError("Choose a service for weighed clothes.")
        if service.price < 0:
            raise ValidationError("Service price must be nonnegative.")
        if service.mode == "kg":
            units = max(kg, settings.min_kg)
        elif service.mode == "load":
            if settings.kg_per_load <= 0:
                raise ValidationError("Kilos per load must be positive.")
            units = max(
                Decimal(1),
                (kg / settings.kg_per_load).to_integral_value(rounding=ROUND_CEILING),
            )
        else:
            raise ValidationError("Unknown pricing unit.")
        lines.append(
            {
                "label": service.name,
                "kind": "base",
                "amount": money(units * service.price),
            }
        )
    for key, raw in data.items():
        if key.startswith("piece_"):
            qty = dec(raw or "0")
            if qty < 0 or qty != qty.to_integral_value() or qty > 9999:
                raise ValidationError(
                    "Piece quantities must be whole numbers from 0 to 9999."
                )
            if qty:
                variant = get_active(
                    PieceVariant, key[6:], active=True, piece_item__archived_at=None
                )
                label = f"{int(qty)} × {variant.piece_item.name} · {variant.label}"
                lines.append(
                    {
                        "label": label,
                        "kind": "piece",
                        "amount": money(qty * variant.price),
                    }
                )
                pieces.append(
                    {"variant": str(variant.id), "label": label, "qty": int(qty)}
                )
    if not kg and not pieces:
        raise ValidationError("Enter clothes weight or at least one piece.")

    def values(k):
        return data.getlist(k) if hasattr(data, "getlist") else data.get(k, [])

    fee_ids = []
    addon_ids = []
    for field, model, kind, amount_field in [
        ("addons", AddOn, "addon", "price"),
        ("fees", Fee, "fee", "amount"),
    ]:
        for key in dict.fromkeys(values(field)):
            obj = get_active(model, key, archived_at=None)
            lines.append(
                {
                    "label": obj.name,
                    "kind": kind,
                    "amount": money(getattr(obj, amount_field)),
                }
            )
            if field == "addons":
                addon_ids.append(str(obj.id))
            if field == "fees":
                fee_ids.append(str(obj.id))
    total = sum((l["amount"] for l in lines), Decimal("0.00"))
    if any(l["amount"] < 0 for l in lines) or total > Decimal("99999999.99"):
        raise ValidationError("Price is outside the supported range.")
    return {
        "kg": kg,
        "service": service if kg else None,
        "pieces": pieces,
        "lines": lines,
        "total": total,
        "fees": fee_ids,
        "addon_ids": addon_ids,
    }


def sheet_time(date, time):
    try:
        dt = datetime.fromisoformat(f"{date}T{time}")
        dt = timezone.make_aware(dt)
    except (ValueError, TypeError):
        raise ValidationError("Enter the sheet date and time.")
    today = timezone.localdate()
    now = timezone.now()
    if dt.date() < today - timedelta(days=7) or dt.date() > today or dt > now:
        raise ValidationError(
            "Sheet time must be today through seven days ago, never in the future."
        )
    return dt


def append_event(branch, type, payload, occurred_at, staff):
    Branch.objects.filter(pk=branch.pk).update(event_seq=F("event_seq") + 1)
    branch.refresh_from_db(fields=["event_seq"])
    return Event.objects.create(
        shop_id=branch.shop_id,
        branch=branch,
        seq=branch.event_seq,
        type=type,
        payload=payload,
        occurred_at=occurred_at,
        actor_staff=staff,
        device=current_device(),
    )


@transaction.atomic
def create_job(data, branch, staff=None):
    branch = Branch.objects.select_for_update().get(pk=branch.pk)
    now = timezone.now()
    received = now
    paid = None
    paper_ref = ""
    paper_date = None
    written = None
    paper = str(data.get("paper", "")) == "1"
    if paper:
        paper_ref = str(data.get("paper_ref", "")).strip().upper()
        if not re.fullmatch(r"P-[1-9][0-9]*", paper_ref):
            raise ValidationError("Enter a P number such as P-7.")
        received = sheet_time(data.get("paper_date"), data.get("received_time"))
        paper_date = received.date()
        existing = Job.objects.filter(
            branch=branch, paper_date=paper_date, paper_ref=paper_ref
        ).first()
        if existing:
            return existing, False
        written = dec(data.get("written_total", ""))
        if written < 0 or written > Decimal("99999999.99") or written != money(written):
            raise ValidationError(
                "Written total must be nonnegative pesos with at most two decimals."
            )
    q = quote(data, branch)
    customer = None
    if data.get("customer"):
        customer = get_active(Customer, data["customer"])
    elif data.get("customer_name", "").strip():
        name = data["customer_name"].strip()
        phone = data.get("customer_phone", "").strip()
        if len(name) > 120 or len(phone) > 40:
            raise ValidationError("Customer name or phone is too long.")
        customer = Customer.objects.create(
            shop_id=branch.shop_id, name=name, phone=phone
        )
    method = data.get("pay_method", "")
    if method not in ("", "cash", "gcash"):
        raise ValidationError("Choose pay at claim, Cash or GCash.")
    if method:
        paid = (
            sheet_time(data.get("paper_date"), data.get("paid_time")) if paper else now
        )
    if paid and paid < received:
        raise ValidationError("Payment cannot precede receipt.")
    ref = data.get("pay_ref", "").strip() if method == "gcash" else ""
    if len(ref) > 120:
        raise ValidationError("GCash reference is too long.")
    Branch.objects.filter(pk=branch.pk).update(job_seq=F("job_seq") + 1)
    branch.refresh_from_db(fields=["job_seq"])
    job = Job.objects.create(
        shop_id=branch.shop_id,
        branch=branch,
        number=branch.job_seq,
        customer=customer,
        service=q["service"],
        kg=q["kg"],
        pieces=q["pieces"],
        fees=q["fees"],
        notes=data.get("notes", ""),
        status=JobStage.objects.get(is_first=True, archived_at=None),
        total=q["total"],
        received_at=received,
        paid_at=paid,
        pay_method=method,
        pay_ref=ref,
        paid_amount=q["total"] if method else 0,
        created_by=staff,
        created_device=current_device(),
        paper_ref=paper_ref,
        paper_date=paper_date,
        written_total=written,
    )
    for line in q["lines"]:
        JobLine.objects.create(shop_id=branch.shop_id, job=job, **line)
    payload = {
        "job_id": str(job.id),
        "number": job.number,
        "total": str(job.total),
        "kg": str(job.kg),
        "pieces": q["pieces"],
        "lines": [{**l, "amount": str(l["amount"])} for l in q["lines"]],
        "from_paper": paper,
        "paper_ref": paper_ref,
        "entered_at": job.created_at.isoformat(),
        "entered_by": actor_name(staff),
        "received_at": received.isoformat(),
        "customer_name": customer.name if customer else "Walk-in",
        "customer_phone": customer.phone if customer else "",
        "notes": job.notes,
        "service_name": q["service"].name if q["service"] else "Pieces only",
    }
    append_event(branch, "job_created", payload, received, staff)
    from supplies.services import deduct_addons

    deduct_addons(branch, job, q["addon_ids"], staff, now)
    if method:
        append_event(
            branch,
            "payment_recorded",
            {
                "job_id": str(job.id),
                "number": job.number,
                "amount": str(job.total),
                "method": method,
                "reference": ref,
                "context": "at drop-off",
                "from_paper": paper,
            },
            paid,
            staff,
        )
    return job, True
