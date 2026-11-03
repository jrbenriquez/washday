"""Switch only the labelled local fixture branch for mode-specific acceptance probes."""

import os, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django

django.setup()
from django.conf import settings
from core.models import Shop, Branch
from core.tenancy import shop_context

if not settings.DEBUG:
    raise SystemExit("Development-only fixture command")
if len(sys.argv) != 2 or sys.argv[1] not in ("simple", "full"):
    raise SystemExit("Pass simple or full")
shop = Shop.objects.get(code="DEV-ONLY")
with shop_context(shop):
    b = Branch.objects.get(code="DEMO")
    b.simple_mode = sys.argv[1] == "simple"
    b.save(update_fields=["simple_mode"])
print("Labelled fixture mode:", sys.argv[1])
