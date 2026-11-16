import uuid

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models

from finance.models import Payment, Sale
from tenants.models import TenantModel

COLOR_VALIDATOR = RegexValidator(r"^#[0-9A-Fa-f]{6}$", "Couleur invalide : utilisez le format #RRGGBB.")
PREFIX_VALIDATOR = RegexValidator(r"^[A-Z0-9]{1,10}$", "Préfixe : 1 à 10 lettres majuscules ou chiffres.")


class DocumentSettings(TenantModel):
    """Personnalisation des factures et reçus : une seule ligne par exploitation."""

    business_name = models.CharField("nom commercial", max_length=150, blank=True)
    address = models.CharField("adresse", max_length=255, blank=True)
    phone = models.CharField("téléphone", max_length=30, blank=True)
    email = models.EmailField("e-mail", blank=True)
    tax_id = models.CharField("NIF", max_length=60, blank=True)
    registry_id = models.CharField("RCCM", max_length=60, blank=True)
    # Chemin RELATIF dans PHOTOS_ROOT : le logo n'a aucune adresse web directe.
    logo_path = models.CharField(max_length=255, blank=True)
    accent_color = models.CharField(
        "couleur principale", max_length=7, default="#1F7A4D", validators=[COLOR_VALIDATOR]
    )
    footer_text = models.TextField("pied de page", blank=True)
    payment_terms = models.TextField("conditions de paiement", blank=True)
    invoice_prefix = models.CharField(max_length=10, default="FAC", validators=[PREFIX_VALIDATOR])
    receipt_prefix = models.CharField(max_length=10, default="REC", validators=[PREFIX_VALIDATOR])

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organization"], name="one_document_settings_per_org"),
        ]

    def __str__(self):
        return f"Paramètres de facturation ({self.organization_id})"


class Document(TenantModel):
    """Facture ou reçu émis. Jamais supprimé ; son contenu est une copie figée à l'émission."""

    class Kind(models.TextChoices):
        INVOICE = "invoice", "Facture"
        RECEIPT = "receipt", "Reçu"

    kind = models.CharField(max_length=10, choices=Kind.choices)
    year = models.PositiveSmallIntegerField("année")
    sequence = models.PositiveIntegerField("numéro d'ordre")
    number = models.CharField("numéro", max_length=30)
    sale = models.ForeignKey(Sale, on_delete=models.PROTECT, related_name="documents")
    payment = models.ForeignKey(
        Payment, null=True, blank=True, on_delete=models.PROTECT, related_name="documents"
    )
    issued_on = models.DateField("date d'émission")
    content = models.JSONField("contenu figé")
    uuid = models.UUIDField(default=uuid.uuid4)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ["-issued_on", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "kind", "year", "sequence"], name="unique_document_sequence"
            ),
            models.UniqueConstraint(fields=["organization", "number"], name="unique_document_number"),
            models.UniqueConstraint(
                fields=["organization", "sale"],
                condition=models.Q(kind="invoice"),
                name="one_invoice_per_sale",
            ),
            models.UniqueConstraint(
                fields=["organization", "payment"],
                condition=models.Q(payment__isnull=False),
                name="one_receipt_per_payment",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(kind="invoice", payment__isnull=True)
                    | models.Q(kind="receipt", payment__isnull=False)
                ),
                name="document_kind_matches_payment",
            ),
        ]
        indexes = [models.Index(fields=["organization", "sale"])]

    def __str__(self):
        return self.number
