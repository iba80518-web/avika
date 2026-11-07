from datetime import timedelta

from django.db.models import Sum
from django.utils import timezone

from farming.models import Cycle, FlockEvent
from farming.services import cycle_summary
from finance.models import Expense, Payment, Sale
from finance.profitability import cycle_birds_sold
from inventory.models import Product
from inventory.services import is_low, stock_snapshot

# Alerte de mortalité (RG-MORT-02) : valeurs fixes pour l'instant, à rendre configurables plus tard.
# Une alerte apparaît si la mortalité du jour atteint au moins MORTALITY_ALERT_MIN poulets
# ET dépasse MORTALITY_ALERT_FACTOR fois la moyenne quotidienne des 7 jours précédents.
MORTALITY_ALERT_FACTOR = 2
MORTALITY_ALERT_MIN = 5
MORTALITY_WINDOW_DAYS = 7


def _sum(queryset, field):
    return queryset.aggregate(total=Sum(field))["total"] or 0


def mortality_alert(cycle, today):
    """Renvoie une alerte (dict) si la mortalité du jour est supérieure à l'habituelle, sinon None.

    Le message ne pose jamais de diagnostic : il constate seulement un écart.
    """
    mortality = FlockEvent.objects.filter(
        cycle=cycle, event_type=FlockEvent.EventType.MORTALITY.value
    )
    today_count = _sum(mortality.filter(event_date=today), "quantity")
    if today_count < MORTALITY_ALERT_MIN:
        return None
    previous = _sum(
        mortality.filter(
            event_date__gte=today - timedelta(days=MORTALITY_WINDOW_DAYS), event_date__lt=today
        ),
        "quantity",
    )
    average = previous / MORTALITY_WINDOW_DAYS
    if today_count <= MORTALITY_ALERT_FACTOR * average:
        return None
    return {
        "cycle": cycle.pk,
        "cycle_name": cycle.name,
        "today": today_count,
        "daily_average": round(average, 1),
        "message": "Mortalité supérieure à l'habituelle.",
    }


def low_stock_products():
    products = []
    for product in Product.objects.filter(is_active=True).order_by("name"):
        quantity, _ = stock_snapshot(product)
        if is_low(product, (quantity, 0)):
            products.append(
                {
                    "id": product.pk,
                    "name": product.name,
                    "stock": str(quantity),
                    "unit": product.base_unit,
                    "threshold": str(product.low_stock_threshold),
                }
            )
    return products


def finance_overview(today):
    """Chiffres du mois en cours et argent à recevoir (toutes ventes valides confondues)."""
    month_start = today.replace(day=1)
    active_sales = Sale.objects.filter(status=Sale.Status.ACTIVE)
    active_payments = Payment.objects.filter(sale__status=Sale.Status.ACTIVE)
    return {
        "month_start": month_start.isoformat(),
        "revenue_month": _sum(active_sales.filter(sale_date__gte=month_start), "total_amount"),
        "collected_month": _sum(active_payments.filter(payment_date__gte=month_start), "amount"),
        "expenses_month": _sum(Expense.objects.filter(expense_date__gte=month_start), "amount"),
        "receivables_total": _sum(active_sales, "total_amount") - _sum(active_payments, "amount"),
    }


def build_dashboard(*, include_stock, include_finance):
    """Tableau de bord de l'exploitation active. Les blocs sensibles sont omis (None) si non autorisés."""
    today = timezone.localdate()

    cycles = []
    alerts = []
    birds_alive = 0
    for cycle in Cycle.objects.filter(status=Cycle.Status.ACTIVE).select_related("coop").order_by(
        "start_date", "id"
    ):
        summary = cycle_summary(cycle)
        birds_alive += summary["current_count"]
        cycles.append(
            {
                "id": cycle.pk,
                "name": cycle.name,
                "coop": cycle.coop.name,
                "start_date": cycle.start_date.isoformat(),
                "day_number": (today - cycle.start_date).days + 1,
                "current_count": summary["current_count"],
                "mortality_rate": summary["mortality_rate"],
                "birds_sold": cycle_birds_sold(cycle),
            }
        )
        alert = mortality_alert(cycle, today)
        if alert is not None:
            alerts.append(alert)

    return {
        "date": today.isoformat(),
        "active_cycles": cycles,
        "birds_alive": birds_alive,
        "mortality_alerts": alerts,
        "low_stock": low_stock_products() if include_stock else None,
        "finance": finance_overview(today) if include_finance else None,
    }
