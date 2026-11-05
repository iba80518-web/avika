from django.db import transaction
from django.db.models import Sum

from farming.models import Cycle

from .models import Expense


class FinanceError(Exception):
    """Règle financière non respectée ; le message est destiné à l'utilisateur."""


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
