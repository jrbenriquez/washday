import time

from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections

from events.sync.client import freeze_and_drain, tick


class Command(BaseCommand):
    help = "Run durable hub replication; use --once for supervision/tests or --retire to freeze and drain."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true")
        parser.add_argument("--retire", action="store_true")
        parser.add_argument(
            "--force",
            action="store_true",
            help="Operator retry ignoring persisted scheduling deadlines.",
        )

    def handle(self, *args, **options):
        if options["retire"]:
            try:
                self.stdout.write(str(freeze_and_drain()))
            except Exception as error:
                raise CommandError(str(error))
            return
        while True:
            try:
                tick(force=options["force"])
            except Exception as error:
                # Do not log URLs, headers, keys, records or sensitive payloads.
                self.stderr.write(
                    "Sync attempt failed ("
                    + type(error).__name__
                    + "); durable events retained for retry."
                )
                if options["once"]:
                    raise CommandError(
                        "Sync attempt failed; check configuration and connectivity."
                    )
            if options["once"]:
                return
            close_old_connections()
            time.sleep(1)
