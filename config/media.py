"""Serve only registered shop logos, including cached logos on offline hubs."""

from pathlib import PurePosixPath

from django.http import FileResponse, Http404
from django.views.decorators.http import require_GET

from core.models import Shop


@require_GET
def logo(request, name):
    shop = Shop.objects.filter(logo=name, archived_at=None).first()
    content_type = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }.get(PurePosixPath(name).suffix.lower())
    if not shop or not content_type:
        raise Http404()
    try:
        return FileResponse(shop.logo.open("rb"), content_type=content_type)
    except FileNotFoundError:
        raise Http404()
