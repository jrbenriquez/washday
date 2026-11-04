import os, sys, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django

django.setup()
from concurrent.futures import ThreadPoolExecutor
from django.db import close_old_connections
from core.models import Shop, Branch
from core.tenancy import shop_context
from catalog.models import SupplyType
from supplies.models import StockEntry, StockCount
from supplies.services import balance, receive, count_stock

shop = Shop.objects.get(code="DEV-ONLY")
with shop_context(shop):
    branch = Branch.objects.get(code="DEMO")
    supply = SupplyType.objects.get(name="DEMO Bag")
    initial = balance(branch, supply)
    previous = set(StockEntry.objects.values_list("id", flat=True))


def worker(n):
    close_old_connections()
    try:
        with shop_context(shop):
            b = Branch.objects.get(pk=branch.pk)
            if n:
                return str(receive(b, supply.id, "1").id)
            return str(
                count_stock(b, {"partial": "1", "count_" + str(supply.id): "50"}).id
            )
    finally:
        close_old_connections()


with ThreadPoolExecutor(max_workers=4) as pool:
    result = list(pool.map(worker, range(4)))
with shop_context(shop):
    count = StockCount.objects.get(pk=result[0])
    line = count.lines.get(supply_type=supply)
    entries = StockEntry.objects.exclude(id__in=previous).filter(
        supply_type=supply, reason="received"
    )
    before = entries.filter(at__lt=count.at).count()
    after = entries.filter(at__gt=count.at).count()
    assert (
        before + after == 3
        and line.expected == initial + before
        and balance(branch, supply) == 50 + after
    )
    print(
        json.dumps(
            {
                "status": "PASS",
                "workers": 4,
                "initial": str(initial),
                "receipts_before_count": before,
                "count_expected": str(line.expected),
                "counted": "50",
                "receipts_after_count": after,
                "final_balance": str(balance(branch, supply)),
            }
        )
    )
