from django.conf import settings
from django.db import models

from core.currencies import CURRENCY_CHOICES
from core.models import TimeStampedModel

from .context import CrossTenantError, TenantContextMissing, get_current_organization_id
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


class TenantManager(models.Manager):
    """Ne renvoie que les objets de l'exploitation active ; refuse de tourner sans elle."""

    def get_queryset(self):
        organization_id = get_current_organization_id()
        if organization_id is None:
            raise TenantContextMissing(
                "Aucune exploitation active. Utilisez organization_context(...) "
                "ou, pour l'administration et les scripts, Model.unscoped."
            )
        return super().get_queryset().filter(organization_id=organization_id)


class TenantModel(TimeStampedModel):
    """Base de toute table métier : appartient obligatoirement à une exploitation."""

    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name="+")

    # Ordre important : le premier gestionnaire déclaré devient le gestionnaire par
    # défaut de Django (administration, validations). `objects` reste, lui, filtré
    # et c'est celui que le code métier doit toujours utiliser.
    unscoped = models.Manager()
    objects = TenantManager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        active_id = get_current_organization_id()
        if self.organization_id is None:
            if active_id is None:
                raise TenantContextMissing(
                    "Impossible d'enregistrer sans exploitation (ni active, ni indiquée)."
                )
            self.organization_id = active_id
        elif active_id is not None and self.organization_id != active_id:
            raise CrossTenantError(
                "Cet objet appartient à une autre exploitation que l'exploitation active."
            )
        super().save(*args, **kwargs)


class Farm(TenantModel):
    """Site d'une exploitation (prépare le multi-sites)."""

    name = models.CharField("nom", max_length=150)
    location = models.CharField("localisation", max_length=255, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organization", "name"], name="unique_farm_name_per_org")
        ]

    def __str__(self):
        return self.name
