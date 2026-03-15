from django.contrib.auth.base_user import BaseUserManager


class StaffManager(BaseUserManager):
    use_in_migrations = False

    def _create_user(self, phone, password, **extra_fields):
        if not phone:
            raise ValueError("The phone field must be set.")

        user = self.model(phone=phone, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, phone, password=None, **extra_fields):
        extra_fields.setdefault("role", "matchmaker")
        extra_fields.setdefault("status", "active")
        return self._create_user(phone, password, **extra_fields)

    def create_superuser(self, phone, password=None, **extra_fields):
        extra_fields.setdefault("role", "admin")
        extra_fields.setdefault("status", "active")
        return self._create_user(phone, password, **extra_fields)
