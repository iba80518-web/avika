import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q

from farming.models import Cycle
from inventory.models import Supplier
from tenants.models import TenantModel


class Customer(TenantModel):
    class CustomerType(models.TextChoices):
        INDIVIDUAL = "individual", "Particulier"
        RESTAURANT = "restaurant", "Restaurant"
        HOTEL = "hotel", "Hôtel"
        WHOLESALER = "wholesaler", "Grossiste"
        RESELLER = "reseller", "Revendeur"
        OTHER = "other", "Autre"

    name = models.CharField("nom", max_length=150)
    phone = models.CharField("téléphone", max_length=20, blank=True)
    address = models.CharField("adresse", max_length=255, blank=True)
    customer_type = models.CharField(
        max_length=20, choices=CustomerType.choices, default=CustomerType.INDIVIDUAL
    )
    is_active = models.BooleanField("actif", default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organization", "name"], name="unique_customer_name_per_org")
        ]

    def __str__(self):
        return self.name


class Expense(TenantModel):
    """Dépense de l'exploitation. L'aliment n'en fait pas partie : il est valorisé par le stock."""

    class Category(models.TextChoices):
        CHICKS = "chicks", "Poussins"
        LABOR = "labor", "Main-d'œuvre"
        TRANSPORT = "transport", "Transport"
        UTILITIES = "utilities", "Eau et électricité"
        EQUIPMENT = "equipment", "Matériel"
        RENT = "rent", "Loyer"
        OTHER = "other", "Autre"

    # Montant entier dans l'unité minimale de la devise de référence de l'exploitation.
    amount = models.BigIntegerField("montant")
    expense_date = models.DateField("date")
    category = models.CharField(max_length=20, choices=Category.choices)
    description = models.CharField(max_length=255, blank=True)
    supplier = models.ForeignKey(
        Supplier, null=True, blank=True, on_delete=models.PROTECT, related_name="expenses"
    )
    # Sans cycle : charge générale de l'exploitation (loyer, salaires communs).
    cycle = models.ForeignKey(
        Cycle, null=True, blank=True, on_delete=models.PROTECT, related_name="expenses"
    )
    uuid = models.UUIDField(default=uuid.uuid4)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organization", "uuid"], name="unique_expense_uuid"),
            models.CheckConstraint(condition=Q(amount__gt=0), name="expense_amount_positive"),
        ]
        indexes = [models.Index(fields=["organization", "expense_date"])]

    def __str__(self):
        return f"{self.get_category_display()} {self.amount} ({self.expense_date})"
