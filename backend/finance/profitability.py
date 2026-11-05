from decimal import ROUND_HALF_UP, Decimal

from django.db.models import Sum

from farming.services import cycle_summary
from inventory.services import cycle_feed_cost

from .models import Sale
from .services import cycle_expense_total, cycle_payments_total, cycle_sales_total


def cycle_birds_sold(cycle):
    """Poulets vendus par des ventes valides (une vente annulée ne compte pas)."""
    total = Sale.objects.filter(cycle=cycle, status=Sale.Status.ACTIVE).aggregate(
        total=Sum("quantity")
    )["total"]
    return total or 0


def _per_bird(amount, birds):
    """Montant par poulet, arrondi à l'unité ; None s'il n'y a aucun poulet."""
    if not birds:
        return None
    return int((Decimal(amount) / Decimal(birds)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def cycle_profitability(cycle):
    """Indicateurs financiers d'un cycle, selon les formules du cahier des charges (Phase 1).

    - chiffre d'affaires  = ventes valides, payées ou non
    - encaissements       = paiements reçus
    - créances            = chiffre d'affaires - encaissements
    - coût de production  = dépenses du cycle + aliment consommé par le cycle
    - résultat            = chiffre d'affaires - coût de production
    - marge (%)           = résultat / chiffre d'affaires x 100
    """
    revenue = cycle_sales_total(cycle)
    collected = cycle_payments_total(cycle)
    expenses = cycle_expense_total(cycle)
    feed_cost = cycle_feed_cost(cycle)
    production_cost = expenses + feed_cost
    result = revenue - production_cost

    summary = cycle_summary(cycle)
    birds_started = summary["initial_count"] + summary["entries"] + summary["transfers_in"]
    birds_sold = cycle_birds_sold(cycle)

    return {
        "cycle": cycle.pk,
        "revenue": revenue,
        "collected": collected,
        "receivables": revenue - collected,
        "expenses": expenses,
        "feed_cost": feed_cost,
        "production_cost": production_cost,
        "result": result,
        "margin_percent": round(result * 100 / revenue, 2) if revenue else None,
        "birds_started": birds_started,
        "birds_sold": birds_sold,
        "cost_per_bird_sold": _per_bird(production_cost, birds_sold),
        "cost_per_bird_started": _per_bird(production_cost, birds_started),
        "current_count": summary["current_count"],
        "mortality_rate": summary["mortality_rate"],
    }
