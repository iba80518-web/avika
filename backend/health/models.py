import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q

from farming.models import Cycle
from inventory.models import Product, StockMovement
from tenants.models import TenantModel


class HealthKind(models.TextChoices):
    VACCINE = "vaccine", "Vaccin"
    TREATMENT = "treatment", "Traitement"
    OTHER = "other", "Autre"


class HealthTemplate(TenantModel):
    """Calendrier type (ex. « Poulet de chair 35 jours »), créé par l'éleveur ou le vétérinaire.

    Aucun protocole médical n'est fourni par défaut : l'application ne prescrit rien.
    """

    name = models.CharField("nom", max_length=150)
    description = models.TextField(blank=True)
    is_active = models.BooleanField("actif", default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organization", "name"], name="unique_health_template_name")
        ]

    def __str__(self):
        return self.name


class HealthTemplateItem(TenantModel):
    """Une ligne du calendrier type : quoi faire, et à quel jour d'âge (jour 0 = jour d'arrivée)."""

    template = models.ForeignKey(HealthTemplate, on_delete=models.PROTECT, related_name="items")
    name = models.CharField("nom", max_length=150)
    kind = models.CharField(max_length=20, choices=HealthKind.choices, default=HealthKind.VACCINE)
    day_of_age = models.PositiveIntegerField("jour d'âge")
    product = models.ForeignKey(
        Product, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["template", "name", "day_of_age"], name="unique_template_item"
            )
        ]

    def __str__(self):
        return f"J{self.day_of_age} : {self.name}"


class HealthTask(TenantModel):
    """Tâche de santé d'un cycle : vaccin ou traitement prévu, puis réalisé (ou annulé)."""

    class Status(models.TextChoices):
        PLANNED = "planned", "À faire"
        DONE = "done", "Réalisée"
        CANCELLED = "cancelled", "Annulée"

    cycle = models.ForeignKey(Cycle, on_delete=models.PROTECT, related_name="health_tasks")
    name = models.CharField("nom", max_length=150)
    kind = models.CharField(max_length=20, choices=HealthKind.choices, default=HealthKind.VACCINE)
    due_date = models.DateField("date prévue")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PLANNED)
    done_date = models.DateField("date de réalisation", null=True, blank=True)
    product = models.ForeignKey(
        Product, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    # Quantité utilisée, dans l'unité de base du produit.
    quantity = models.DecimalField(max_digits=14, decimal_places=3, null=True, blank=True)
    # Sortie de stock créée à la réalisation (si l'éleveur a choisi de décrémenter le stock).
    stock_movement = models.OneToOneField(
        StockMovement, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    note = models.CharField(max_length=255, blank=True)
    uuid = models.UUIDField(default=uuid.uuid4)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organization", "uuid"], name="unique_health_task_uuid"),
            models.CheckConstraint(
                condition=~Q(status="done") | Q(done_date__isnull=False),
                name="health_task_done_has_date",
            ),
        ]
        indexes = [models.Index(fields=["organization", "status", "due_date"])]

    def __str__(self):
        return f"{self.name} ({self.due_date})"
