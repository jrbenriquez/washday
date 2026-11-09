from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import Shop


class Command(BaseCommand):
    help = (
        "Reopen owner onboarding for a test shop without deleting its data. "
        "Both the shop name and code must contain 'test' (case-insensitive)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--shop-code", required=True,
            help="Exact Shop code (not a branch code).",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Validate the test-shop guard and show the target without changing it.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            # Use the same shop lock as onboarding saves, including the safety check.
            shop = Shop.objects.select_for_update().get(code=options["shop_code"])
        except Shop.DoesNotExist:
            raise CommandError("Shop not found. --shop-code must be an exact Shop code, not a branch code.")
        if "test" not in shop.name.casefold() or "test" not in shop.code.casefold():
            raise CommandError(
                "Reset refused: both the shop name and shop code must contain 'test' "
                "(case-insensitive). No data was changed."
            )
        if shop.archived_at:
            raise CommandError("Reset refused: this shop is archived. No data was changed.")
        target = f"{shop.name!r} (shop code: {shop.code})"
        if options["dry_run"]:
            self.stdout.write(f"Dry run: {target} is eligible. No data was changed.")
            return
        if shop.onboarding_completed_at is None:
            self.stdout.write(f"Onboarding is already pending for {target}.")
        else:
            # Owner-only metadata: avoid the shop post-save hook, which would
            # otherwise increment operational settings and trigger replication.
            Shop.objects.filter(pk=shop.pk).update(onboarding_completed_at=None)
            self.stdout.write(self.style.SUCCESS(f"Onboarding reset for {target}."))
        self.stdout.write(
            "The owner will see setup on their next owner workspace visit. "
            "Existing catalog, settings, branches, jobs, staff and devices are preserved."
        )
