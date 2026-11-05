from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core.models import Branch
from core.tenancy import shop_context
from events.sync.modes import activate_direct, activate_hub, prepare


class Command(BaseCommand):
    help = "Cloud operator: prepare a hub key or switch a drained branch writer after closing."

    def add_arguments(self, parser):
        parser.add_argument("branch_id")
        parser.add_argument("action", choices=["prepare", "hub", "direct"])
        parser.add_argument("--expected-seq", type=int)
        parser.add_argument("--hub-url")

    def handle(self, *args, **options):
        if settings.APP_ROLE != "cloud":
            raise CommandError("Run this on the cloud database.")
        branch = Branch.unscoped.filter(pk=options["branch_id"]).first()
        if not branch:
            raise CommandError("Unknown branch.")
        with shop_context(branch.shop_id):
            try:
                if options["action"] == "prepare":
                    from urllib.parse import urlsplit

                    public = options["hub_url"] or ""
                    url = urlsplit(public)
                    if (
                        not url.hostname
                        or (
                            url.scheme != "https"
                            and not (
                                settings.DEBUG
                                and url.scheme == "http"
                                and url.hostname in ("localhost", "127.0.0.1", "::1")
                            )
                        )
                        or url.username
                        or url.password
                        or url.query
                        or url.fragment
                        or url.path not in ("", "/")
                    ):
                        raise CommandError(
                            "Pass --hub-url with the HTTPS hub origin (loopback HTTP only in development)."
                        )
                    branch.hub_url = public.rstrip("/")
                    branch.save(update_fields=["hub_url"])
                    self.stdout.write(prepare(branch))
                else:
                    if options["expected_seq"] is None:
                        raise CommandError("Pass the verified --expected-seq.")
                    (activate_hub if options["action"] == "hub" else activate_direct)(
                        branch, options["expected_seq"]
                    )
                    self.stdout.write(
                        "Writer switched. Re-enrol branch devices at the new address."
                    )
            except Exception as error:
                raise CommandError(str(error))
