from django.conf import settings
from django.db.backends.signals import connection_created
from django.db.models import F
from django.db.models.signals import post_save

from events.records import CATALOG


def connection_ready(sender, connection, **kwargs):
    if settings.APP_ROLE == "hub" and connection.vendor == "sqlite":
        with connection.cursor() as cursor:
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=FULL")


def configuration_changed(sender, instance, raw=False, **kwargs):
    if (
        raw
        or settings.APP_ROLE != "cloud"
        or sender._meta.label_lower
        not in set(CATALOG + ("core.branch", "core.shop")) - {"core.settings"}
    ):
        return
    from core.models import Settings

    shop_id = (
        instance.pk if sender._meta.label_lower == "core.shop" else instance.shop_id
    )
    Settings.objects.filter(shop_id=shop_id).update(version=F("version") + 1)


def register():
    connection_created.connect(connection_ready, dispatch_uid="washday.sqlite-wal")
    post_save.connect(
        configuration_changed, dispatch_uid="washday.configuration-version"
    )
