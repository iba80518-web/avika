from django.conf import settings
from django.db import models

from core.currencies import CURRENCY_CHOICES
from core.models import TimeStampedModel

from .roles import PERMISSION_CHOICES, Role


class Organization(TimeStampedModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspendue"

    name = models.CharField("nom de l'exploitation", max_length=150)
    phone = models.CharField("téléphone", max_length=20, blank=True)
    address = models.CharField("adresse", max_length=255, blank=True)
    region = models.CharField("région", max_length=100, blank=True)
    prefecture = models.CharField("préfecture", max_length=100, blank=True)
    commune = models.CharField("commune", max_length=100, blank=True)
    description = models.TextField("description", blank=True)
    reference_currency = models.CharField(
        "devise de référence", max_length=3, choices=CURRENCY_CHOICES, default="GNF"
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)

    def __str__(self):
        return self.name


class Membership(TimeStampedModel):
    """Lie un utilisateur à une exploitation, avec son rôle."""

    class Status(models.TextChoices):
        ACTIVE = "active", "Actif"
        INVITED = "invited", "Invité"
        SUSPENDED = "suspended", "Suspendu"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships"
    )
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="memberships"
    )
    role = models.CharField(max_length=20, choices=Role.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "organization"], name="unique_membership_per_org")
        ]

    def __str__(self):
        return f"{self.user} - {self.organization} ({self.get_role_display()})"


class MembershipPermission(TimeStampedModel):
    """Exception à la matrice du rôle : accorde ou retire une permission à un membre."""

    membership = models.ForeignKey(
        Membership, on_delete=models.CASCADE, related_name="permission_overrides"
    )
    permission = models.CharField(max_length=40, choices=PERMISSION_CHOICES)
    granted = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["membership", "permission"], name="unique_override_per_membership"
            )
        ]

    def __str__(self):
        return f"{self.membership} : {self.permission}={self.granted}"


class TenantModel(TimeStampedModel):
    """Base de toute table métier : appartient obligatoirement à une exploitation."""

    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name="+")

    class Meta:
        abstract = True
