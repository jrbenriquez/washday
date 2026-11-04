from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.db import transaction
from core.models import Shop, ShopOwner
from core.tenancy import shop_context


class Command(BaseCommand):
    help = "Allow a verified Google email for one existing shop. Creates no password or login session."

    def add_arguments(self, p):
        p.add_argument("email")
        p.add_argument("--shop-code", required=True)

    @transaction.atomic
    def handle(self, *args, **options):
        email = options["email"].strip().casefold()
        try:
            validate_email(email)
        except ValidationError:
            raise CommandError("Enter a valid Google email.")
        try:
            shop = Shop.objects.get(code=options["shop_code"], archived_at=None)
        except Shop.DoesNotExist:
            raise CommandError(
                "Shop not found; migrate and provision/seed the local shop first."
            )
        existing = ShopOwner.unscoped.filter(email__iexact=email).first()
        if existing and existing.shop_id != shop.pk:
            raise CommandError("That email already belongs to another shop.")
        with shop_context(shop):
            if existing:
                existing.active = True
                existing.save(update_fields=["active"])
            else:
                ShopOwner.objects.create(shop=shop, email=email)
        self.stdout.write("Google owner email allow-listed. Sign in at /owner/login/.")
