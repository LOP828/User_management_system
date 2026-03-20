from django.core.management.base import BaseCommand

from apps.notify.services import send_due_reminder_notifications


class Command(BaseCommand):
    help = "Send persisted due reminders once for WeCom smoke validation."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=100,
            help="Maximum number of pending persisted reminders to send in one run.",
        )

    def handle(self, *args, **options):
        result = send_due_reminder_notifications(limit=options["limit"])
        self.stdout.write(self.style.SUCCESS(str(result)))

