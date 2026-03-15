import os

from django.core.management.base import BaseCommand, CommandError

from apps.staff.models import Staff


class Command(BaseCommand):
    help = "Create or update the default admin account from environment variables."

    def handle(self, *args, **options):
        phone = os.getenv("INIT_ADMIN_PHONE")
        name = os.getenv("INIT_ADMIN_NAME")
        password = os.getenv("INIT_ADMIN_PASSWORD")
        wechat_id = os.getenv("INIT_ADMIN_WECHAT_ID")

        missing = [
            env_name
            for env_name, value in (
                ("INIT_ADMIN_PHONE", phone),
                ("INIT_ADMIN_NAME", name),
                ("INIT_ADMIN_PASSWORD", password),
            )
            if not value
        ]
        if missing:
            raise CommandError(f"Missing required environment variables: {', '.join(missing)}")

        staff, created = Staff.objects.get_or_create(
            phone=phone,
            defaults={
                "name": name,
                "role": Staff.ROLE_ADMIN,
                "status": Staff.STATUS_ACTIVE,
                "wechat_id": wechat_id,
            },
        )

        changed_fields = []
        for field, value in (
            ("name", name),
            ("role", Staff.ROLE_ADMIN),
            ("status", Staff.STATUS_ACTIVE),
            ("wechat_id", wechat_id),
        ):
            if getattr(staff, field) != value:
                setattr(staff, field, value)
                changed_fields.append(field)

        staff.set_password(password)
        changed_fields.append("password")
        staff.save(update_fields=[*changed_fields, "updated_at"])

        action = "created" if created else "updated"
        self.stdout.write(self.style.SUCCESS(f"Default admin {action}: {staff.phone}"))
