from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.db.models import Q

from core.models import TimeStampedModel


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email=None, phone=None, password=None, **extra_fields):
        if not email and not phone:
            raise ValueError("Un email ou un téléphone est obligatoire.")
        email = self.normalize_email(email) if email else None
        user = self.model(email=email, phone=phone or None, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email=email, password=password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin, TimeStampedModel):
    email = models.EmailField("email", unique=True, null=True, blank=True)
    phone = models.CharField("téléphone", max_length=20, unique=True, null=True, blank=True)
    full_name = models.CharField("nom complet", max_length=150)
    is_active = models.BooleanField("actif", default=True)
    is_staff = models.BooleanField("accès à l'administration", default=False)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(email__isnull=False) | Q(phone__isnull=False),
                name="user_email_or_phone_required",
            )
        ]

    def save(self, *args, **kwargs):
        # Une chaîne vide deviendrait un doublon : on enregistre NULL à la place.
        self.email = self.email or None
        self.phone = self.phone or None
        super().save(*args, **kwargs)

    def __str__(self):
        return self.full_name or self.email or self.phone or f"Utilisateur {self.pk}"
