import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q

from farming.models import Cycle, ImmutableRecordError
from tenants.models import TenantModel


class Supplier(TenantModel):
    class Category(models.TextChoices):
        CHICKS = "chicks", "Poussins"
        FEED = "feed", "Aliments"
        VACCINES = "vaccines", "Vaccins"
        MEDICINES = "medicines", "Médicaments"
        EQUIPMENT = "equipment", "Matériel"
        OTHER = "other", "Autre"

    name = models.CharField("nom", max_length=150)
    phone = models.CharField("téléphone", max_length=20, blank=True)
    address = models.CharField("adresse", max_length=255, blank=True)
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.OTHER)
    is_active = models.BooleanField("actif", default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organization", "name"], name="unique_supplier_name_per_org")
        ]

    def __str__(self):
        return self.name


class Product(TenantModel):
    class ProductType(models.TextChoices):
        FEED = "feed", "Aliment"
        VACCINE = "vaccine", "Vaccin"
        MEDICINE = "medicine", "Médicament"
        EQUIPMENT = "equipment", "Matériel"
        PACKAGING = "packaging", "Emballage"
        OTHER = "other", "Autre"

    name = models.CharField("nom", max_length=150)
    product_type = models.CharField(max_length=20, choices=ProductType.choices)
    base_unit = models.CharField("unité de base", max_length=20)  # ex. kg
    low_stock_threshold = models.DecimalField(
        "seuil de stock faible", max_digits=14, decimal_places=3, default=0
    )
    is_active = models.BooleanField("actif", default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organization", "name"], name="unique_product_name_per_org"),
            models.CheckConstraint(condition=Q(low_stock_threshold__gte=0), name="product_threshold_valid"),
        ]

    def __str__(self):
        return self.name


class ProductUnit(TenantModel):
    """Unité de saisie d'un produit : 1 sac = 50 (unité de base)."""

    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="units")
    name = models.CharField("nom", max_length=20)
    factor_to_base = models.DecimalField(max_digits=12, decimal_places=3)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["product", "name"], name="unique_unit_name_per_product"),
            models.CheckConstraint(condition=Q(factor_to_base__gt=0), name="unit_factor_positive"),
        ]

    def __str__(self):
        return f"{self.name} ({self.factor_to_base} {self.product.base_unit})"


class StockMovement(TenantModel):
    """Mouvement de stock : immuable. La quantité est toujours en unité de base."""

    class MovementType(models.TextChoices):
        ENTRY = "entry", "Entrée"
        EXIT = "exit", "Sortie"
        LOSS = "loss", "Perte"
        ADJUSTMENT = "adjustment", "Correction"

    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="movements")
    movement_type = models.CharField(max_length=20, choices=MovementType.choices)
    # Positive, sauf pour une correction (positive ou négative, jamais nulle).
    quantity = models.DecimalField(max_digits=14, decimal_places=3)
    # Valeur du mouvement (toujours >= 0), dans la devise de référence, unité minimale.
    total_cost = models.BigIntegerField(default=0)
    movement_date = models.DateField("date")
    cycle = models.ForeignKey(
        Cycle, null=True, blank=True, on_delete=models.PROTECT, related_name="stock_movements"
    )
    note = models.TextField(blank=True)
    uuid = models.UUIDField(default=uuid.uuid4)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organization", "uuid"], name="unique_stock_movement_uuid"),
            models.CheckConstraint(condition=Q(total_cost__gte=0), name="stock_movement_cost_valid"),
            models.CheckConstraint(
                condition=(Q(movement_type="adjustment") & ~Q(quantity=0))
                | (~Q(movement_type="adjustment") & Q(quantity__gt=0)),
                name="stock_movement_quantity_valid",
            ),
        ]
        indexes = [models.Index(fields=["organization", "product", "movement_date"])]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ImmutableRecordError("Un mouvement de stock ne peut pas être modifié.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ImmutableRecordError("Un mouvement de stock ne peut pas être supprimé.")
