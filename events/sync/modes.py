import hashlib
import secrets

from django.core.exceptions import ValidationError
from django.db import transaction

from core.models import Branch
from events.models import HubCredential, Inbox


@transaction.atomic
def prepare(branch):
    branch = Branch.objects.select_for_update().get(pk=branch.pk)
    if branch.mode != "direct":
        raise ValidationError("Prepare a hub while the branch is still direct.")
    token = secrets.token_urlsafe(48)
    HubCredential.objects.update_or_create(
        branch=branch,
        defaults={
            "shop_id": branch.shop_id,
            "key_hash": hashlib.sha256(token.encode()).hexdigest(),
            "epoch": branch.writer_epoch + 1,
            "state": "prepared",
            "bootstrap_seq": None,
            "last_seen_at": None,
        },
    )
    return token


@transaction.atomic
def activate_hub(branch, expected_seq):
    branch = Branch.objects.select_for_update().get(pk=branch.pk)
    credential = HubCredential.objects.select_for_update().get(branch=branch)
    if (
        branch.mode != "direct"
        or credential.state != "prepared"
        or credential.bootstrap_seq != branch.event_seq
        or expected_seq != branch.event_seq
    ):
        raise ValidationError(
            "Bootstrap must exactly match the final direct sequence. Re-bootstrap after closing."
        )
    branch.mode = "hub"
    branch.writer_epoch = credential.epoch
    branch.save(update_fields=["mode", "writer_epoch"])
    credential.state = "active"
    credential.save(update_fields=["state"])


@transaction.atomic
def activate_direct(branch, expected_seq):
    branch = Branch.objects.select_for_update().get(pk=branch.pk)
    credential = HubCredential.objects.select_for_update().get(branch=branch)
    if (
        branch.mode != "hub"
        or credential.state != "frozen"
        or expected_seq != branch.event_seq
        or Inbox.objects.filter(branch=branch, applied_at=None).exists()
    ):
        raise ValidationError(
            "Freeze and fully drain the hub before activating direct service."
        )
    branch.mode = "direct"
    branch.writer_epoch += 1
    branch.save(update_fields=["mode", "writer_epoch"])
    credential.state = "retired"
    credential.save(update_fields=["state"])
