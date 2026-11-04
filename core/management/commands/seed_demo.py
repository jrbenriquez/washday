from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db import transaction
from django.contrib.auth.hashers import make_password
from core.models import Shop, Branch, Settings, JobStage, MachineCategory, Machine
from core.tenancy import shop_context
from catalog.models import Service, AddOn, Fee, PieceItem, PieceVariant
from people.models import Staff
from catalog.models import SupplyType, AddOnUse
from supplies.models import StockEntry
from supplies.services import receive


class Command(BaseCommand):
    help = "Create labelled local test fixtures. Never use for production operating values."

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("seed_demo is development-only")
        shop, _ = Shop.objects.get_or_create(
            code="DEV-ONLY", defaults={"name": "Ivan & Ivy Laundry · DEMO"}
        )
        with shop_context(shop):
            branch, _ = Branch.objects.get_or_create(
                code="DEMO",
                defaults={
                    "shop": shop,
                    "name": "DEMO branch · not operating data",
                    "number": 1,
                },
            )
            Settings.objects.get_or_create(
                shop=shop, defaults={"min_kg": "3.0", "kg_per_load": "7.0"}
            )
            washer, _ = MachineCategory.objects.get_or_create(
                shop=shop,
                name="Washer",
                defaults={
                    "label_prefix": "W",
                    "uses_wash_supplies": True,
                    "sort_order": 0,
                },
            )
            dryer, _ = MachineCategory.objects.get_or_create(
                shop=shop, name="Dryer", defaults={"label_prefix": "D", "sort_order": 1}
            )
            for category, label in [(washer, "W1"), (washer, "W2"), (dryer, "D1")]:
                Machine.objects.get_or_create(
                    shop=shop,
                    branch=branch,
                    label=label,
                    defaults={"category": category},
                )
            for i, name in enumerate(
                ["Received", "Washing", "Drying", "Folding", "Ready"]
            ):
                JobStage.objects.get_or_create(
                    shop=shop,
                    sort_order=i,
                    defaults={
                        "name": name,
                        "is_first": i == 0,
                        "is_last": i == 4,
                        "ask_for_machine": i in (1, 2),
                        "move_on_when_unloaded": i == 2,
                    },
                )
            for name, category in [("Washing", washer), ("Drying", dryer)]:
                stage = JobStage.objects.get(name=name)
                stage.machine_category = category
                stage.save(update_fields=["machine_category"])
            for name, mode, price in [
                ("DEMO Wash-dry-fold", "kg", "35.00"),
                ("DEMO Per load", "load", "150.00"),
                ("DEMO Heavy items", "kg", "90.00"),
            ]:
                Service.objects.get_or_create(
                    shop=shop, name=name, defaults={"mode": mode, "price": price}
                )
            AddOn.objects.get_or_create(
                shop=shop, name="DEMO Extra rinse", defaults={"price": "20.00"}
            )
            Fee.objects.get_or_create(
                shop=shop, name="Rush", defaults={"note": "Same day", "amount": "50.00"}
            )
            item, _ = PieceItem.objects.get_or_create(shop=shop, name="DEMO Comforter")
            for label, price in [("Single", "120.00"), ("Queen", "180.00")]:
                PieceVariant.objects.get_or_create(
                    shop=shop, piece_item=item, label=label, defaults={"price": price}
                )
            staff, _ = Staff.objects.get_or_create(
                shop=shop,
                branch=branch,
                name="DEMO staff",
                defaults={"pin_hash": make_password(None)},
            )
        with shop_context(shop):
            detergent, _ = SupplyType.objects.get_or_create(
                shop=shop,
                name="DEMO Detergent",
                defaults={"unit": "cup", "low_level": "3", "per_washer_load": "0.5"},
            )
            bag, _ = SupplyType.objects.get_or_create(
                shop=shop,
                name="DEMO Bag",
                defaults={"unit": "piece", "low_level": "5", "per_packed_job": "1"},
            )
            addon = AddOn.objects.get(name="DEMO Extra rinse")
            AddOnUse.objects.get_or_create(
                shop=shop, addon=addon, supply_type=detergent, defaults={"qty": "0.25"}
            )
            for supply in [detergent, bag]:
                if not StockEntry.objects.filter(
                    branch=branch, supply_type=supply
                ).exists():
                    receive(branch, supply.id, "100", staff)
        self.stdout.write(
            f"DEVELOPMENT ONLY. All prices/names except brand and Rush are labelled fixtures.\nENABLE_DEV_BRANCH_SCOPE=1 DEV_BRANCH_ID={branch.id} DEV_STAFF_ID={staff.id} uv run python manage.py runserver 127.0.0.1:8000"
        )
