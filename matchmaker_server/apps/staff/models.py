from django.contrib.auth.base_user import AbstractBaseUser
from django.db import models

from apps.staff.managers import StaffManager


class Staff(AbstractBaseUser):
    ROLE_MATCHMAKER = "matchmaker"
    ROLE_ADMIN = "admin"
    ROLE_CHOICES = (
        (ROLE_MATCHMAKER, "matchmaker"),
        (ROLE_ADMIN, "admin"),
    )

    STATUS_ACTIVE = "active"
    STATUS_DISABLED = "disabled"
    STATUS_CHOICES = (
        (STATUS_ACTIVE, "active"),
        (STATUS_DISABLED, "disabled"),
    )

    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=50)
    phone = models.CharField(max_length=20, unique=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    wechat_id = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = StaffManager()

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = ["name"]

    class Meta:
        db_table = "staff"
        indexes = [
            models.Index(fields=["role"], name="staff_role_idx"),
        ]

    def __str__(self):
        return f"{self.name}<{self.phone}>"

    @property
    def is_active(self):
        return self.status == self.STATUS_ACTIVE

    @property
    def is_staff(self):
        return self.role == self.ROLE_ADMIN

    def has_perm(self, perm, obj=None):
        return self.is_staff

    def has_module_perms(self, app_label):
        return self.is_staff
