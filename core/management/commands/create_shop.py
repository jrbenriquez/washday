import sys
from io import StringIO
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction

from core.models import JobStage, MachineCategory, Settings, Shop
from core.tenancy import shop_context


class Command(BaseCommand):
    help = "Provision a shop with settings and workflow, and optionally approve its Google owner email."

    def add_arguments(self, parser):
        parser.add_argument(
            "--shop-code", required=True, help="Unique Shop code (not a branch code)."
        )
        parser.add_argument("--name", required=True, help="Shop name.")
        parser.add_argument(
            "--min-kg", required=True, help="Minimum billable kilos (zero or more)."
        )
        parser.add_argument(
            "--kg-per-load", required=True, help="Kilos per load (greater than zero)."
        )
        parser.add_argument(
            "--timezone",
            default="Asia/Manila",
            help="IANA timezone (default: Asia/Manila).",
        )
        parser.add_argument(
            "--owner-email",
            help="Google email to approve; otherwise prompted in a terminal.",
        )
        parser.add_argument(
            "--noinput",
            "--no-input",
            action="store_false",
            dest="interactive",
            help="Skip the optional owner-email prompt.",
        )

    def handle(self, *args, **options):
        shop = Shop(
            code=options["shop_code"].strip(),
            name=options["name"].strip(),
            timezone=options["timezone"].strip(),
        )
        try:
            ZoneInfo(shop.timezone)
        except (ZoneInfoNotFoundError, ValueError):
            raise CommandError("Enter a valid IANA timezone, such as Asia/Manila.")

        config = Settings(
            shop=shop, min_kg=options["min_kg"], kg_per_load=options["kg_per_load"]
        )
        try:
            # Validate before prompting, without holding a database write lock.
            # Rerunning must never overwrite an existing (even archived) shop.
            shop.full_clean()
            config.full_clean(exclude=["shop"])
        except ValidationError as exc:
            raise CommandError("; ".join(exc.messages)) from exc
        if config.min_kg < 0 or config.kg_per_load <= 0:
            raise CommandError(
                "--min-kg must be zero or more; --kg-per-load must be positive."
            )

        email = options["owner_email"]
        if email is None and options["interactive"] and sys.stdin.isatty():
            try:
                email = input("Owner's Google email (leave blank to skip): ").strip()
            except (EOFError, KeyboardInterrupt):
                raise CommandError("Shop creation cancelled; no records were saved.")

        owner_output = StringIO()
        try:
            with transaction.atomic():
                shop.save()
                with shop_context(shop):
                    config.save()
                    washer = MachineCategory.objects.create(
                        shop=shop,
                        name="Washer",
                        label_prefix="W",
                        uses_wash_supplies=True,
                        sort_order=0,
                    )
                    dryer = MachineCategory.objects.create(
                        shop=shop, name="Dryer", label_prefix="D", sort_order=1
                    )
                    for order, name in enumerate(
                        ["Received", "Washing", "Drying", "Folding", "Ready"]
                    ):
                        category = {"Washing": washer, "Drying": dryer}.get(name)
                        JobStage.objects.create(
                            shop=shop,
                            name=name,
                            sort_order=order,
                            is_first=order == 0,
                            is_last=order == 4,
                            ask_for_machine=category is not None,
                            machine_category=category,
                            move_on_when_unloaded=name == "Drying",
                        )

                    if email:
                        call_command(
                            "allow_owner",
                            email,
                            shop_code=shop.code,
                            stdout=owner_output,
                        )
        except ValidationError as exc:
            raise CommandError("; ".join(exc.messages)) from exc
        except IntegrityError as exc:
            raise CommandError(
                "Shop creation conflicted with an existing record; no records were saved."
            ) from exc

        self.stdout.write(self.style.SUCCESS(f"Created shop {shop.code}: {shop.name}."))
        if owner_output.getvalue():
            self.stdout.write(owner_output.getvalue(), ending="")
        else:
            self.stdout.write(
                "No owner email approved. Use allow_owner with this Shop's --shop-code when ready."
            )
        self.stdout.write(
            "Next: in the owner workspace, add branches, prices, machines and staff, and review operational settings before taking jobs."
        )
