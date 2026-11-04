from django.core.management.base import BaseCommand, CommandError
from backups.worker import run_due


class Command(BaseCommand):
    help = "Process due Google Drive exports. Invoke every minute from cron or a platform scheduler."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=20)

    def handle(self, *args, **options):
        if options["limit"] < 1:
            raise CommandError("--limit must be positive")
        count = run_due(options["limit"])
        self.stdout.write(
            f"Completed {count} export(s). See Owner > Drive exports for per-run status."
        )
