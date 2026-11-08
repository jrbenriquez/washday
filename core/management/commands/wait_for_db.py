import time

from django.core.management.base import BaseCommand, CommandError
from django.db import OperationalError, connection


class Command(BaseCommand):
    help = "Wait for PostgreSQL connectivity before applying startup migrations."
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument("--timeout", type=float, default=60)

    def handle(self, *args, **options):
        timeout = options["timeout"]
        if timeout < 0:
            raise CommandError("Timeout must be non-negative.")
        if connection.vendor != "postgresql":
            return
        deadline = time.monotonic() + timeout
        announced = False
        while True:
            try:
                connection.ensure_connection()
            except OperationalError:
                connection.close()
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise CommandError(
                        "Database connection did not become ready within the startup timeout. "
                        "Check the private network, database availability, and PG settings."
                    ) from None
                if not announced:
                    self.stdout.write("Waiting for database connection before migrations...")
                    announced = True
                time.sleep(min(1, remaining))
            else:
                connection.close()
                self.stdout.write("Database connection ready.")
                return
