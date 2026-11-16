from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import Max, Sum
from django.utils import timezone

from audit.services import log_action, snapshot
from finance.models import Payment, Sale
from finance.services import paid_total, sale_balance

from .models import Document, DocumentSettings

# Champs que le propriétaire peut modifier (le logo a son propre envoi sécurisé).
EDITABLE_FIELDS = [
    "business_name", "address", "phone", "email", "tax_id", "registry_id",
    "accent_color", "footer_text", "payment_terms", "invoice_prefix", "receipt_prefix",
]
SETTINGS_FIELDS = EDITABLE_FIELDS + ["logo_path"]
DOCUMENT_FIELDS = ["kind", "number", "sale_id", "payment_id", "issued_on"]


class DocumentError(Exception):
    """Règle non respectée ; le message est destiné à l'utilisateur."""


def get_settings():
    """Paramètres de l'exploitation active ; créés avec leurs valeurs par défaut au premier appel."""
    row = DocumentSettings.objects.first()
    if row is None:
        try:
            with transaction.atomic():
                row = DocumentSettings.objects.create()
        except IntegrityError:  # une autre requête vient de les créer
            row = DocumentSettings.objects.get()
    return row


def _lock_settings():
    """Verrouille la ligne de paramètres : c'est ce verrou qui rend la numérotation sans doublon."""
    return DocumentSettings.objects.select_for_update().get(pk=get_settings().pk)


@transaction.atomic
def update_settings(*, user=None, **changes):
    unknown = set(changes) - set(EDITABLE_FIELDS)
    if unknown:
        raise DocumentError("Réglage inconnu : " + ", ".join(sorted(unknown)) + ".")
    row = _lock_settings()
    before = snapshot(row, SETTINGS_FIELDS)
    for key, value in changes.items():
        value = value.strip() if isinstance(value, str) else value
        if key in ("invoice_prefix", "receipt_prefix") and isinstance(value, str):
            value = value.upper()
        setattr(row, key, value)
    try:
        row.full_clean(exclude=["organization", "logo_path"])
    except DjangoValidationError as error:
        messages = [text for texts in error.message_dict.values() for text in texts]
        raise DocumentError(" ".join(messages))
    row.save()
    log_action(
        user=user,
        action="document_settings.updated",
        obj=row,
        summary="Paramètres des factures et reçus modifiés",
        before=before,
        after=snapshot(row, SETTINGS_FIELDS),
    )
    return row


def _issuer(row, organization):
    """Coordonnées de l'émetteur au moment de l'émission ; l'exploitation sert de repli."""
    return {
        "name": row.business_name or organization.name,
        "address": row.address or organization.address,
        "phone": row.phone or organization.phone,
        "email": row.email,
        "tax_id": row.tax_id,
        "registry_id": row.registry_id,
        "logo_path": row.logo_path,
        "accent_color": row.accent_color,
        "footer_text": row.footer_text,
        "payment_terms": row.payment_terms,
    }


def _customer(sale, name=""):
    """Le client enregistré ; sinon le nom saisi à l'émission (client de passage) ; sinon rien."""
    if sale.customer_id is None:
        name = (name or "").strip()
        return {"name": name, "phone": "", "address": ""} if name else None
    return {
        "name": sale.customer.name,
        "phone": sale.customer.phone,
        "address": sale.customer.address,
    }


def _lines(sale):
    """Les lignes de la vente, déjà formulées pour le client."""
    if sale.product == Sale.Product.EGGS:
        tier = " (gros)" if sale.price_tier == Sale.PriceTier.WHOLESALE else " (détail)"
        if sale.egg_unit == Sale.EggUnit.EGG:
            label, unit = "Œufs" + tier, "œuf(s)"
        elif sale.egg_unit == Sale.EggUnit.TRAY:
            label, unit = f"Œufs, plateau de {sale.eggs_per_unit}" + tier, "plateau(x)"
        else:
            label, unit = f"Œufs, carton de {sale.eggs_per_unit}" + tier, "carton(s)"
        quantity = str(sale.quantity)
    elif sale.sale_type == Sale.SaleType.WEIGHT:
        label, unit = f"Poulets vendus au poids ({sale.quantity} sujets)", "kg"
        quantity = str(sale.weight_kg.normalize()) if sale.weight_kg is not None else "0"
    else:
        label, unit, quantity = "Poulets", "sujet(s)", str(sale.quantity)
    return [
        {
            "label": label,
            "quantity": quantity,
            "unit": unit,
            "unit_price": sale.unit_price,
            "total": sale.total_amount,
        }
    ]


def _sale_section(sale):
    return {
        "id": sale.pk,
        "date": sale.sale_date.isoformat(),
        "cycle": sale.cycle.name,
        "lines": _lines(sale),
        "total": sale.total_amount,
        "note": sale.note,
    }


def _allocate(kind, year, row):
    """Numéro suivant. À appeler seulement quand le verrou des paramètres est tenu."""
    last = Document.objects.filter(kind=kind, year=year).aggregate(last=Max("sequence"))["last"] or 0
    sequence = last + 1
    prefix = row.invoice_prefix if kind == Document.Kind.INVOICE else row.receipt_prefix
    return sequence, f"{prefix}-{year}-{sequence:04d}"


def _create(kind, *, sale, payment, content, row, user):
    today = timezone.localdate()
    sequence, number = _allocate(kind, today.year, row)
    document = Document.objects.create(
        kind=kind,
        year=today.year,
        sequence=sequence,
        number=number,
        sale=sale,
        payment=payment,
        issued_on=today,
        content=content,
        created_by=user,
    )
    log_action(
        user=user,
        action="document.issued",
        obj=document,
        summary=f"{document.get_kind_display()} {number} émis(e) pour la vente {sale.pk}",
        after=snapshot(document, DOCUMENT_FIELDS),
    )
    return document


@transaction.atomic
def issue_invoice(sale, *, user=None, customer_name=""):
    """Émet la facture d'une vente. Renvoie (document, créé) : une seule facture par vente."""
    row = _lock_settings()
    locked = Sale.objects.select_for_update().get(pk=sale.pk)
    existing = Document.objects.filter(kind=Document.Kind.INVOICE, sale=locked).first()
    if existing is not None:
        return existing, False
    if locked.status != Sale.Status.ACTIVE:
        raise DocumentError("Cette vente est annulée : aucune facture ne peut être émise.")

    paid = paid_total(locked)
    content = {
        "currency": locked.organization.reference_currency,
        "issuer": _issuer(row, locked.organization),
        "customer": _customer(locked, customer_name),
        "sale": _sale_section(locked),
        "paid": paid,
        "balance": sale_balance(locked),
    }
    document = _create(
        Document.Kind.INVOICE, sale=locked, payment=None, content=content, row=row, user=user
    )
    return document, True


@transaction.atomic
def issue_receipt(payment, *, user=None, customer_name=""):
    """Émet le reçu d'un paiement. Renvoie (document, créé) : un seul reçu par paiement."""
    row = _lock_settings()
    locked = Sale.objects.select_for_update().get(pk=payment.sale_id)
    existing = Document.objects.filter(kind=Document.Kind.RECEIPT, payment=payment).first()
    if existing is not None:
        return existing, False
    if locked.status != Sale.Status.ACTIVE:
        raise DocumentError("Cette vente est annulée : aucun reçu ne peut être émis.")

    # Cumul payé jusqu'à ce paiement inclus : le reçu dit où en était la vente à ce moment-là.
    paid_after = (
        Payment.objects.filter(sale=locked, pk__lte=payment.pk).aggregate(total=Sum("amount"))["total"]
        or 0
    )
    content = {
        "currency": locked.organization.reference_currency,
        "issuer": _issuer(row, locked.organization),
        "customer": _customer(locked, customer_name),
        "sale": _sale_section(locked),
        "payment": {
            "id": payment.pk,
            "amount": payment.amount,
            "date": payment.payment_date.isoformat(),
            "method": payment.get_method_display(),
        },
        "paid": paid_after,
        "balance": locked.total_amount - paid_after,
    }
    document = _create(
        Document.Kind.RECEIPT, sale=locked, payment=payment, content=content, row=row, user=user
    )
    return document, True
