import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q

from core.currencies import CURRENCY_CHOICES
from tenants.models import Farm, TenantModel


class ImmutableRecordError(Exception):
    """Un événement du journal ne se modifie ni ne se supprime : on le corrige par un autre."""


class Coop(TenantModel):
    """Poulailler."""

    class Type(models.TextChoices):
        BROILER = "broiler", "Poulets de chair"
        LAYER = "layer", "Pondeuses"
        OTHER = "other", "Autre"

    class Status(models.TextChoices):
        ACTIVE = "active", "Actif"
        INACTIVE = "inactive", "Inactif"

    farm = models.ForeignKey(Farm, on_delete=models.PROTECT, related_name="coops")
    name = models.CharField("nom", max_length=150)
    capacity = models.PositiveIntegerField("capacité")
    type = models.CharField(max_length=20, choices=Type.choices, default=Type.BROILER)
    location = models.CharField("localisation", max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    description = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organization", "name"], name="unique_coop_name_per_org"),
            models.CheckConstraint(condition=Q(capacity__gt=0), name="coop_capacity_positive"),
        ]

    def __str__(self):
        return self.name


class Cycle(TenantModel):
    """Cycle d'élevage dans un poulailler."""

    class Status(models.TextChoices):
        PLANNED = "planned", "Planifié"
        ACTIVE = "active", "En cours"
        COMPLETED = "completed", "Terminé"
        CANCELLED = "cancelled", "Annulé"

    coop = models.ForeignKey(Coop, on_delete=models.PROTECT, related_name="cycles")
    name = models.CharField("nom", max_length=150)
    type = models.CharField(max_length=20, choices=Coop.Type.choices, default=Coop.Type.BROILER)
    start_date = models.DateField("date de début")
    end_date = models.DateField("date de fin", null=True, blank=True)
    initial_count = models.PositiveIntegerField("effectif initial")
    supplier_name = models.CharField("fournisseur", max_length=150, blank=True)
    unit_price = models.BigIntegerField("prix d'achat unitaire", default=0)  # unité minimale
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default="GNF")
    target = models.CharField("objectif", max_length=255, blank=True)
    planned_sale_date = models.DateField("date de vente prévue", null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PLANNED)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "coop", "name"], name="unique_cycle_name_per_coop"
            ),
            models.CheckConstraint(condition=Q(initial_count__gt=0), name="cycle_initial_count_positive"),
            models.UniqueConstraint(
                fields=["coop"],
                condition=Q(status="active"),
                name="one_active_cycle_per_coop",
            ),
        ]

    def __str__(self):
        return self.name


class FlockEvent(TenantModel):
    """Journal du cheptel : source de vérité de l'effectif. Immuable."""

    class EventType(models.TextChoices):
        ENTRY = "entry", "Entrée"
        MORTALITY = "mortality", "Mortalité"
        SALE = "sale", "Vente"
        TRANSFER_IN = "transfer_in", "Transfert entrant"
        TRANSFER_OUT = "transfer_out", "Transfert sortant"
        CORRECTION = "correction", "Correction"

    cycle = models.ForeignKey(Cycle, on_delete=models.PROTECT, related_name="events")
    event_type = models.CharField(max_length=20, choices=EventType.choices)
    # Toujours positif, sauf pour une correction (positive ou négative, jamais nulle).
    quantity = models.IntegerField("quantité")
    event_date = models.DateField("date")
    cause = models.CharField("cause supposée", max_length=150, blank=True)
    note = models.TextField("observation", blank=True)
    uuid = models.UUIDField(default=uuid.uuid4)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organization", "uuid"], name="unique_flock_event_uuid"),
            models.CheckConstraint(
                condition=(Q(event_type="correction") & ~Q(quantity=0))
                | (~Q(event_type="correction") & Q(quantity__gt=0)),
                name="flock_event_quantity_valid",
            ),
        ]
        indexes = [models.Index(fields=["organization", "cycle", "event_date"])]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ImmutableRecordError("Un événement du journal ne peut pas être modifié.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ImmutableRecordError("Un événement du journal ne peut pas être supprimé.")
