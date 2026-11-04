"""Use real SQLite locking so the concurrency test runs in the full suite."""

import os
import tempfile
from pathlib import Path

from .settings import *  # noqa: F403

if DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3":  # noqa: F405
    DATABASES["default"]["TEST"] = {  # noqa: F405
        "NAME": str(Path(tempfile.gettempdir()) / f"washday-test-{os.getpid()}.sqlite3")
    }
