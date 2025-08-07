from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.db import models
from accounts.abstracts import (
    UniversalIdModel,
    MemberNumberModel,
    TimeStampedModel,
    ReferenceModel,
)


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("The given email must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)

        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        extra_fields.setdefault("is_active", True)

        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self._create_user(email, password, **extra_fields)


class User(
    AbstractBaseUser,
    PermissionsMixin,
    UniversalIdModel,
    MemberNumberModel,
    TimeStampedModel,
    ReferenceModel,
):

    # Personal Details
    salutation = models.CharField(max_length=25)
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    email = models.EmailField()
    dob = models.DateField()

    # Identity
    id_type = models.CharField(max_length=255)
    id_no = models.CharField(max_length=255)
    tax_pin = models.CharField(max_length=255)

    # Contact & Address Details
    phone = models.CharField(max_length=255)
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
    REQUIRED_FIELDS = ["email", "password"]

    objects = UserManager()

    def __str__(self):
        return self.member_no
