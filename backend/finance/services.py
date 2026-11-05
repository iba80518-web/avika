from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from farming.models import Cycle, FlockEvent
from farming.services import FarmingError, record_event

from .models import Expense, Payment, Sale


class FinanceError(Exception):
    """Règle financière non respectée ; le message est destiné à l'utilisateur."""


# ---------------------------------------------------------------- dépenses


def cycle_expense_total(cycle):
    """Somme des dépenses imputées à un cycle (hors aliment, valorisé par le stock)."""
    total = Expense.objects.filter(cycle=cycle).aggregate(total=Sum("amount"))["total"]
    return total or 0


@transaction.atomic
def record_expense(
    *,
    amount,
    expense_date,
    category,
    description="",
    supplier=None,
    cycle=None,
    user=None,
    uuid=None,
):
    """Ajoute une dépense. Renvoie (dépense, créée).

    Un uuid déjà reçu ne crée pas de doublon (synchronisation hors connexion).
    """
    if uuid is not None:
        existing = Expense.objects.filter(uuid=uuid).first()
        if existing is not None:
            if (existing.amount, existing.category, existing.cycle_id) != (
                amount,
                category,
                cycle.pk if cycle is not None else None,
            ):
                raise FinanceError("Cet identifiant d'opération a déjà servi pour autre chose.")
            return existing, False

    if amount is None or amount <= 0:
        raise FinanceError("Le montant doit être supérieur à 0.")
    if supplier is not None and not supplier.is_active:
        raise FinanceError("Ce fournisseur est désactivé.")
    if cycle is not None and cycle.status == Cycle.Status.CANCELLED:
        raise FinanceError("Ce cycle est annulé.")

    extra = {"uuid": uuid} if uuid is not None else {}
    expense = Expense.objects.create(
        amount=amount,
        expense_date=expense_date,
        category=category,
        description=description,
        supplier=supplier,
        cycle=cycle,
        created_by=user,
        **extra,
    )
    return expense, True


# ------------------------------------------------------- ventes, paiements


def compute_total(sale_type, quantity, weight_kg, unit_price):
    """Total d'une vente : calculé ici, jamais fourni par le client (RG-VEN-01)."""
    if sale_type == Sale.SaleType.WEIGHT:
        raw = Decimal(weight_kg) * unit_price
        return int(raw.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return quantity * unit_price


def paid_total(sale):
    total = Payment.objects.filter(sale=sale).aggregate(total=Sum("amount"))["total"]
    return total or 0


def sale_balance(sale):
    """Reste à payer d'une vente (0 si elle est annulée)."""
    if sale.status != Sale.Status.ACTIVE:
        return 0
    return sale.total_amount - paid_total(sale)


def cycle_sales_total(cycle):
    """Chiffre d'affaires du cycle : ventes valides, payées ou non."""
    total = Sale.objects.filter(cycle=cycle, status=Sale.Status.ACTIVE).aggregate(
        total=Sum("total_amount")
    )["total"]
    return total or 0


def cycle_payments_total(cycle):
    """Encaissements du cycle : paiements reçus sur les ventes valides."""
    total = Payment.objects.filter(
        sale__cycle=cycle, sale__status=Sale.Status.ACTIVE
    ).aggregate(total=Sum("amount"))["total"]
    return total or 0


@transaction.atomic
def record_sale(
    *,
    cycle,
    sale_date,
    sale_type,
    quantity,
    unit_price,
    customer=None,
    weight_kg=None,
    paid_amount=0,
    payment_method=Payment.Method.CASH,
    user=None,
    note="",
    uuid=None,
):
    """Enregistre une vente, retire les poulets de l'effectif et note l'éventuel paiement.

    Renvoie (vente, créée). Un uuid déjà reçu ne crée pas de doublon.
    """
    if uuid is not None:
        existing = Sale.objects.filter(uuid=uuid).first()
        if existing is not None:
            if (existing.cycle_id, existing.quantity, existing.unit_price) != (
                cycle.pk,
                quantity,
                unit_price,
            ):
                raise FinanceError("Cet identifiant d'opération a déjà servi pour autre chose.")
            return existing, False

    if quantity is None or quantity <= 0:
        raise FinanceError("Le nombre de poulets doit être supérieur à 0.")
    if unit_price is None or unit_price <= 0:
        raise FinanceError("Le prix unitaire doit être supérieur à 0.")
    if sale_type == Sale.SaleType.WEIGHT:
        if weight_kg is None or weight_kg <= 0:
            raise FinanceError("Le poids total est obligatoire pour une vente au poids.")
    else:
        weight_kg = None

    total = compute_total(sale_type, quantity, weight_kg, unit_price)
    if total <= 0:
        raise FinanceError("Le montant total de la vente doit être supérieur à 0.")
    if paid_amount is None or paid_amount < 0 or paid_amount > total:
        raise FinanceError("Le montant payé doit être compris entre 0 et le total de la vente.")
    if paid_amount < total and customer is None:
        raise FinanceError("Une vente non payée en totalité doit avoir un client.")
    if customer is not None and not customer.is_active:
        raise FinanceError("Ce client est désactivé.")

    # Retire les poulets de l'effectif ; refuse si le cycle n'est pas en cours,
    # si la date précède le cycle ou si l'effectif devient négatif.
    extra = {"uuid": uuid} if uuid is not None else {}
    try:
        event, _ = record_event(
            cycle=cycle,
            event_type=FlockEvent.EventType.SALE.value,
            quantity=quantity,
            event_date=sale_date,
            user=user,
            note=note,
            **extra,
        )
    except FarmingError as error:
        raise FinanceError(str(error))

    sale = Sale.objects.create(
        customer=customer,
        cycle=cycle,
        sale_date=sale_date,
        sale_type=sale_type,
        quantity=quantity,
        weight_kg=weight_kg,
        unit_price=unit_price,
        total_amount=total,
        flock_event=event,
        note=note,
        created_by=user,
        **extra,
    )
    if paid_amount > 0:
        Payment.objects.create(
            sale=sale,
            amount=paid_amount,
            payment_date=sale_date,
            method=payment_method,
            created_by=user,
        )
    return sale, True


@transaction.atomic
def record_payment(
    *, sale, amount, payment_date, method=Payment.Method.CASH, user=None, uuid=None
):
    """Ajoute un paiement à une vente. Renvoie (paiement, créé)."""
    # Verrouille la vente : deux paiements simultanés ne peuvent pas dépasser le reste à payer.
    locked = Sale.objects.select_for_update().get(pk=sale.pk)

    if uuid is not None:
        existing = Payment.objects.filter(uuid=uuid).first()
        if existing is not None:
            if (existing.sale_id, existing.amount) != (locked.pk, amount):
                raise FinanceError("Cet identifiant d'opération a déjà servi pour autre chose.")
            return existing, False

    if locked.status != Sale.Status.ACTIVE:
        raise FinanceError("Cette vente est annulée.")
    if amount is None or amount <= 0:
        raise FinanceError("Le montant doit être supérieur à 0.")
    if payment_date < locked.sale_date:
        raise FinanceError("La date du paiement précède celle de la vente.")
    balance = sale_balance(locked)
    if amount > balance:
        raise FinanceError(f"Le paiement dépasse le reste à payer ({balance}).")

    extra = {"uuid": uuid} if uuid is not None else {}
    payment = Payment.objects.create(
        sale=locked,
        amount=amount,
        payment_date=payment_date,
        method=method,
        created_by=user,
        **extra,
    )
    return payment, True


@transaction.atomic
def cancel_sale(sale, *, user=None, reason=""):
    """Annule une vente : les poulets reviennent dans l'effectif par un événement de correction."""
    locked = Sale.objects.select_for_update().select_related("cycle").get(pk=sale.pk)
    if locked.status != Sale.Status.ACTIVE:
        raise FinanceError("Cette vente est déjà annulée.")
    if Payment.objects.filter(sale=locked).exists():
        raise FinanceError(
            "Cette vente a déjà reçu des paiements : elle ne peut pas être annulée."
        )

    text = f"Annulation de la vente {locked.pk}."
    if reason:
        text = f"{text} {reason}"
    try:
        event, _ = record_event(
            cycle=locked.cycle,
            event_type=FlockEvent.EventType.CORRECTION.value,
            quantity=locked.quantity,
            event_date=max(timezone.localdate(), locked.sale_date),
            user=user,
            note=text,
        )
    except FarmingError as error:
        raise FinanceError(str(error))

    locked.status = Sale.Status.CANCELLED
    locked.cancel_event = event
    locked.save(update_fields=["status", "cancel_event", "updated_at"])
    return locked
