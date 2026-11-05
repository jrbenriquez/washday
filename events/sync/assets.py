"""Cache the authenticated shop logo locally before a hub goes offline."""

import base64
import hashlib
from pathlib import PurePosixPath

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage


def export_logo(shop):
    if not shop.logo or shop.logo.name.startswith("img/"):
        return None
    with shop.logo.open("rb") as stream:
        content = stream.read(2 * 1024 * 1024 + 1)
    if len(content) > 2 * 1024 * 1024:
        raise ValidationError("Shop logo exceeds supported offline asset size.")
    return {
        "name": shop.logo.name,
        "sha256": hashlib.sha256(content).hexdigest(),
        "content": base64.b64encode(content).decode(),
    }


def import_logo(document):
    asset = document.get("logo_asset")
    if not asset:
        return
    name = asset["name"]
    parts = PurePosixPath(name)
    if (
        parts.is_absolute()
        or ".." in parts.parts
        or not name.startswith("shops/" + document["shop"]["id"] + "/logos/")
        or name != document["shop"]["logo"]
    ):
        raise ValidationError("Invalid shop asset path.")
    content = base64.b64decode(asset["content"], validate=True)
    if (
        len(content) > 2 * 1024 * 1024
        or hashlib.sha256(content).hexdigest() != asset["sha256"]
    ):
        raise ValidationError("Shop asset failed verification.")
    if default_storage.exists(name):
        with default_storage.open(name, "rb") as stream:
            if hashlib.sha256(stream.read()).hexdigest() == asset["sha256"]:
                return
        raise ValidationError("Existing asset differs from its immutable name.")
    default_storage.save(name, ContentFile(content))
