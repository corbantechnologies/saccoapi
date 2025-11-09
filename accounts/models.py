from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.db import models
from cloudinary.models import CloudinaryField

from accounts.abstracts import (
    UniversalIdModel,
    MemberNumberModel,
    TimeStampedModel,
    ReferenceModel,
)


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, password, **extra_fields):
        user = self.model(**extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_user(self, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        extra_fields.setdefault("is_active", True)

        return self._create_user(password, **extra_fields)

    def create_superuser(self, password, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_approved", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        if extra_fields.get("is_approved") is not True:
            raise ValueError("Superuser must have is_approved=True.")

        return self._create_user(password, **extra_fields)


class User(
    AbstractBaseUser,
    PermissionsMixin,
    UniversalIdModel,
    MemberNumberModel,
    TimeStampedModel,
    ReferenceModel,
):

    # Personal Details
    salutation = models.CharField(max_length=25, blank=True, null=True)
    first_name = models.CharField(max_length=255)
    middle_name = models.CharField(max_length=255, blank=True, null=True)
    last_name = models.CharField(max_length=255)
    email = models.EmailField(blank=True, null=True)
    dob = models.DateField(blank=True, null=True)
    gender = models.CharField(max_length=255)
    avatar = CloudinaryField("avatars", blank=True, null=True)

    # Identity
    id_type = models.CharField(max_length=255, blank=True, null=True)
    id_number = models.CharField(max_length=255, blank=True, null=True)
    tax_pin = models.CharField(max_length=255, blank=True, null=True)

    # Contact & Address Details
    phone = models.CharField(max_length=25, blank=True, null=True)
    county = models.CharField(max_length=255, blank=True, null=True)

    # Employment Status
    employment_type = models.CharField(max_length=255)
    employer = models.CharField(max_length=255, blank=True, null=True)
    job_title = models.CharField(max_length=255, blank=True, null=True)

    # Account status
    is_approved = models.BooleanField(default=False)

    # Permissions
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    is_member = models.BooleanField(default=True)
    is_system_admin = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    USERNAME_FIELD = "member_no"
    REQUIRED_FIELDS = [
        "password",
        "salutation",
        "first_name",
        "last_name",
        "gender",
        "employment_type",
    ]

    objects = UserManager()

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.member_no} - {self.first_name} {self.last_name}"
