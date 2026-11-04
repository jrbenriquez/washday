"""Transaction-local deltas shared by Undo and the hub outbox.

Signals observe saves only inside an explicitly recorded business operation.
Each immutable Event drains the pending delta; no request or browser snapshots.
"""

from contextvars import ContextVar
from functools import wraps

from django.conf import settings
from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.utils import timezone

from people.context import current_device

from .records import OPERATIONAL, fields

_recorder = ContextVar("operation_recorder", default=None)
_last_action = ContextVar("last_reversible_receipt", default=None)


def last_action():
    return _last_action.get()


class Recorder:
    def __init__(self):
        self.changes = {}
        self.pending = {}
        self.events = []


def before_save(sender, instance, raw=False, **kwargs):
    recorder = _recorder.get()
    if raw or recorder is None or sender._meta.label_lower not in OPERATIONAL:
        return
    key = (sender._meta.label_lower, str(instance.pk))
    if key not in recorder.changes:
        old = (
            sender.objects.filter(pk=instance.pk).first()
            if not instance._state.adding
            else None
        )
        recorder.changes[key] = {
            "model": key[0],
            "before": fields(old) if old else None,
            "after": None,
        }


def after_save(sender, instance, raw=False, **kwargs):
    recorder = _recorder.get()
    if raw or recorder is None or sender._meta.label_lower not in OPERATIONAL:
        return
    key = (sender._meta.label_lower, str(instance.pk))
    recorder.changes[key]["after"] = fields(instance)
    recorder.pending[key] = {"model": key[0], "fields": fields(instance)}


def register():
    pre_save.connect(before_save, dispatch_uid="washday.journal.before")
    post_save.connect(after_save, dispatch_uid="washday.journal.after")


def event_written(event):
    if (
        getattr(settings, "APP_ROLE", "cloud") == "cloud"
        and event.branch.mode != "direct"
    ):
        from django.core.exceptions import ValidationError

        raise ValidationError("Operational writes for this branch belong to its hub.")
    recorder = _recorder.get()
    if recorder is None:
        if getattr(settings, "APP_ROLE", "cloud") == "hub":
            from django.core.exceptions import ValidationError

            raise ValidationError(
                "Hub events must be written through a recorded business operation."
            )
        return
    recorder.events.append(event)
    if getattr(settings, "APP_ROLE", "cloud") == "hub":
        from .sync.authority import assert_writer

        assert_writer(event.branch)
        from core.models import Branch

        from .models import Outbox

        branch = Branch.objects.get(pk=event.branch_id)
        Outbox.objects.create(
            shop_id=event.shop_id,
            event=event,
            frame={
                "protocol": 1,
                "event": fields(event),
                "records": list(recorder.pending.values()),
                "job_seq": branch.job_seq,
                "epoch": branch.writer_epoch,
            },
        )
    recorder.pending.clear()


def recorded_action(function):
    @wraps(function)
    def call(*args, **kwargs):
        if _recorder.get() is not None:
            return function(*args, **kwargs)
        recorder = Recorder()
        _last_action.set(None)
        token = _recorder.set(recorder)
        try:
            with transaction.atomic():
                result = function(*args, **kwargs)
                if recorder.events and function.__name__ in REVERSIBLE:
                    from .models import Action

                    last = recorder.events[-1]
                    receipt = Action.objects.create(
                        shop_id=last.shop_id,
                        branch_id=last.branch_id,
                        device=current_device(),
                        staff=last.actor_staff,
                        event=last,
                        first_seq=recorder.events[0].seq,
                        kind=function.__name__,
                        changes=list(recorder.changes.values()),
                        created_at=timezone.now(),
                    )
                    _last_action.set(receipt)
                return result
        finally:
            _recorder.reset(token)

    return call


REVERSIBLE = {
    "advance",
    "override",
    "claim",
    "receive",
    "count_stock",
    "start_for_job",
    "self_service",
    "unload",
}
