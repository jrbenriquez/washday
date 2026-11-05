import hashlib
import json

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from core.models import Branch
from events.models import Event, HubCredential, Inbox

from .schema import apply_record, decode


def digest(frame):
    return hashlib.sha256(
        json.dumps(frame, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


@transaction.atomic
def push(credential, frames, retire=False, last_seq=None):
    if not 0 <= len(frames) <= 500:
        raise ValidationError("Send at most 500 events per batch.")
    branch = Branch.objects.select_for_update().get(pk=credential.branch_id)
    credential = HubCredential.objects.select_for_update().get(pk=credential.pk)
    if (
        branch.mode != "hub"
        or credential.state != "active"
        or credential.epoch != branch.writer_epoch
    ):
        raise ValidationError("This hub is fenced or not the active branch writer.")
    for frame in frames:
        if (
            frame.get("protocol") != 1
            or frame.get("epoch") != credential.epoch
            or not isinstance(frame.get("records"), list)
        ):
            raise ValidationError("Unsupported protocol or writer epoch.")
        event = decode(Event, frame["event"])
        if (
            event["branch_id"] != branch.id
            or event["shop_id"] != branch.shop_id
            or event["seq"] <= 0
        ):
            raise ValidationError("Event scope is invalid.")
        for field in ("device_id", "actor_staff_id"):
            if event[field]:
                from events.sync.schema import related_branch

                cls = Event._meta.get_field(field[:-3]).remote_field.model
                obj = cls.objects.filter(pk=event[field]).first()
                from .schema import actor_belongs

                historical_actor = (
                    obj is not None
                    and field == "actor_staff_id"
                    and actor_belongs(obj, branch)
                )
                if not obj or (
                    related_branch(obj) != branch.pk and not historical_actor
                ):
                    raise ValidationError("Event actor belongs to another branch.")
        existing = Inbox.objects.filter(branch=branch, seq=event["seq"]).first()
        if existing:
            if existing.event_id != event["id"] or existing.digest != digest(frame):
                raise ValidationError("Conflicting event replay.")
            continue
        if (
            Event.objects.filter(pk=event["id"]).exists()
            or event["seq"] <= branch.event_seq
        ):
            raise ValidationError("Event conflicts with existing branch history.")
        Inbox.objects.create(
            shop_id=branch.shop_id,
            branch=branch,
            event_id=event["id"],
            seq=event["seq"],
            frame=frame,
            digest=digest(frame),
        )
    while True:
        item = Inbox.objects.filter(
            branch=branch, seq=branch.event_seq + 1, applied_at=None
        ).first()
        if not item:
            break
        for record in item.frame["records"]:
            apply_record(record, branch)
        data = decode(Event, item.frame["event"])
        event = Event(**data)
        event.save_base(raw=True, force_insert=True)
        branch.event_seq = item.seq
        branch.job_seq = max(branch.job_seq, int(item.frame["job_seq"]))
        Branch.objects.filter(pk=branch.pk).update(
            event_seq=branch.event_seq, job_seq=branch.job_seq
        )
        item.applied_at = timezone.now()
        item.save(update_fields=["applied_at"])
    credential.last_seen_at = timezone.now()
    if retire:
        if (
            last_seq != branch.event_seq
            or Inbox.objects.filter(branch=branch, applied_at=None).exists()
        ):
            raise ValidationError("Drain every event before retiring this writer.")
        credential.state = "frozen"
    credential.save(update_fields=["last_seen_at", "state"])
    return {
        "acknowledged_seq": branch.event_seq,
        "epoch": branch.writer_epoch,
        "state": credential.state,
    }
