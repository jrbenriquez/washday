"""Start only the labelled local fixture branch; never a production entry point."""

import os, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django

django.setup()
from django.conf import settings
from core.models import Shop, Branch
from core.tenancy import shop_context
from people.models import Staff

if not settings.DEBUG:
    raise SystemExit("Development-only command")
shop = Shop.objects.get(code="DEV-ONLY")
with shop_context(shop):
    branch = Branch.objects.get(code="DEMO")
    staff = Staff.objects.filter(branch=branch, active=True).first()
os.environ["ENABLE_DEV_BRANCH_SCOPE"] = "1"
os.environ["DEV_BRANCH_ID"] = str(branch.id)
os.environ["DEV_STAFF_ID"] = str(staff.id)
os.execv(
    sys.executable,
    [sys.executable, "manage.py", "runserver", "127.0.0.1:8000", "--noreload"],
)
