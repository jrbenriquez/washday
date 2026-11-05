"""Restart-safe worker; short transactions never hold locks over network I/O."""

import json
from datetime import timedelta
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from core.models import Branch, Settings
from core.tenancy import shop_context
from events.models import Outbox, Replica

from .catalog import apply_configuration


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValidationError("Sync does not follow redirects with hub credentials.")


class Transport:
    def __init__(self):
        self.base = settings.HUB_CLOUD_URL.rstrip("/")
        parsed = urlsplit(self.base)
        local = parsed.hostname in ("localhost", "127.0.0.1", "::1")
        if parsed.scheme != "https" and not (
            settings.DEBUG and parsed.scheme == "http" and local
        ):
            raise ValidationError(
                "Use HTTPS for the cloud URL; loopback HTTP is development-only."
            )
        if (
            parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.path not in ("", "/")
            or not settings.HUB_KEY
        ):
            raise ValidationError("Configure HUB_KEY and a plain cloud origin URL.")

    def __call__(self, path, data=None):
        request = Request(
            self.base + path,
            data=json.dumps(data).encode() if data is not None else None,
            headers={
                "Authorization": "Bearer " + settings.HUB_KEY,
                "Content-Type": "application/json",
            },
        )
        with build_opener(NoRedirect()).open(request, timeout=15) as response:
            return json.load(response)


def bootstrap(transport):
    if settings.APP_ROLE != "hub":
        raise ValidationError("Bootstrap runs only in hub role.")
    document = transport("/sync/bootstrap/")
    return apply_configuration(document, initial=True)


def tick(transport=None, now=None, force=False):
    if settings.APP_ROLE != "hub":
        raise ValidationError("Sync worker runs only in hub role.")
    transport = transport or Transport()
    now = now or timezone.now()
    if not Branch.unscoped.filter(pk=settings.HUB_BRANCH_ID).exists():
        bootstrap(transport)
    branch = Branch.unscoped.select_related("shop").get(pk=settings.HUB_BRANCH_ID)
    with shop_context(branch.shop_id):
        replica = Replica.objects.get(branch=branch)
        if force:
            replica.push_due = None
            replica.pull_due = None
        if replica.failures and replica.push_due and replica.push_due > now:
            return
        try:
            if not replica.pull_due or replica.pull_due <= now:
                config = Settings.objects.get(shop_id=branch.shop_id)
                document = transport(
                    "/sync/pull/?" + urlencode({"since": config.version})
                )
                if document.get("unchanged"):
                    if (
                        document.get("protocol") != 1
                        or document.get("version") != config.version
                        or document.get("branch_id") != str(branch.pk)
                        or document.get("epoch") != branch.writer_epoch
                    ):
                        raise ValidationError("Invalid unchanged-settings binding.")
                    Replica.objects.filter(pk=replica.pk).update(
                        writer_active=bool(document.get("active"))
                        and not replica.frozen
                    )
                else:
                    apply_configuration(document)
                Replica.objects.filter(pk=replica.pk).update(
                    pull_due=now + timedelta(minutes=5)
                )
                replica.refresh_from_db()
                branch.refresh_from_db()
            if not force and replica.push_due and replica.push_due > now:
                return
            if branch.mode != "hub" or not replica.writer_active or replica.frozen:
                return
            frames = list(
                Outbox.objects.filter(
                    event__branch=branch, event__seq__gt=replica.acknowledged_seq
                )
                .select_related("event")
                .order_by("event__seq")[:500]
            )
            if any(
                frame.event.seq != replica.acknowledged_seq + offset
                for offset, frame in enumerate(frames, 1)
            ):
                raise ValidationError(
                    "Outbox contains a missing event; no acknowledgement can skip it."
                )
            response = transport("/sync/push/", {"events": [o.frame for o in frames]})
            acknowledged = response["acknowledged_seq"]
            maximum = frames[-1].event.seq if frames else replica.acknowledged_seq
            if (
                response.get("epoch") != branch.writer_epoch
                or not isinstance(acknowledged, int)
                or not replica.acknowledged_seq <= acknowledged <= maximum
            ):
                raise ValidationError(
                    "Cloud acknowledgement is outside the submitted contiguous range."
                )
            expected = replica.acknowledged_seq
            for frame in frames:
                if frame.event.seq > acknowledged:
                    break
                if frame.event.seq != expected + 1:
                    raise ValidationError("Outbox contains a missing event.")
                expected = frame.event.seq
            if expected != acknowledged:
                raise ValidationError("Acknowledgement skipped a missing event.")
            with transaction.atomic():
                locked = Replica.objects.select_for_update().get(pk=replica.pk)
                # A concurrent worker may already have advanced this cursor.
                if acknowledged >= locked.acknowledged_seq:
                    Outbox.objects.filter(
                        event__branch=branch, event__seq__lte=acknowledged, sent_at=None
                    ).update(sent_at=now)
                    more = Outbox.objects.filter(
                        event__branch=branch, event__seq__gt=acknowledged
                    ).exists()
                    locked.acknowledged_seq = acknowledged
                    locked.failures = 0
                    locked.push_due = now if more else now + timedelta(seconds=30)
                    locked.save(
                        update_fields=["acknowledged_seq", "failures", "push_due"]
                    )
        except Exception:
            failures = min(replica.failures + 1, 16)
            Replica.objects.filter(pk=replica.pk).update(
                failures=failures,
                push_due=now + timedelta(seconds=min(30 * 2 ** (failures - 1), 900)),
            )
            raise


def freeze_and_drain(transport=None):
    transport = transport or Transport()
    branch = Branch.unscoped.get(pk=settings.HUB_BRANCH_ID)
    with shop_context(branch.shop_id):
        with transaction.atomic():
            branch = Branch.objects.select_for_update().get(pk=branch.pk)
            replica = Replica.objects.select_for_update().get(branch=branch)
            replica.frozen = True
            replica.writer_active = False
            replica.save(update_fields=["frozen", "writer_active"])
        # New writes are now fenced locally, including concurrent HTTP requests.
        while True:
            replica.refresh_from_db()
            frames = list(
                Outbox.objects.filter(
                    event__branch=branch, event__seq__gt=replica.acknowledged_seq
                )
                .select_related("event")
                .order_by("event__seq")[:500]
            )
            if not frames:
                break
            response = transport("/sync/push/", {"events": [o.frame for o in frames]})
            if (
                response.get("epoch") != branch.writer_epoch
                or response.get("acknowledged_seq") != frames[-1].event.seq
            ):
                raise ValidationError(
                    "Cloud did not acknowledge the complete drain batch."
                )
            Replica.objects.filter(pk=replica.pk).update(
                acknowledged_seq=response["acknowledged_seq"]
            )
            Outbox.objects.filter(
                event__branch=branch,
                event__seq__lte=response["acknowledged_seq"],
                sent_at=None,
            ).update(sent_at=timezone.now())
        if replica.acknowledged_seq != branch.event_seq:
            raise ValidationError("A missing outbox event prevents migration.")
        return transport(
            "/sync/push/", {"events": [], "retire": True, "last_seq": branch.event_seq}
        )
