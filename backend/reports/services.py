from urllib.parse import quote

from django.utils import timezone

from farming.models import Cycle
from farming.services import cycle_summary
from finance.profitability import cycle_profitability
from health.services import reminders


def _money(amount, currency):
    text = f"{amount:,}".replace(",", " ")
    return f"{text} {currency}".strip()


def _percent(value):
    return "—" if value is None else f"{round(float(value), 1)} %"


def cycle_report_text(cycle, *, include_finance=False, include_profits=False, include_health=False):
    """Message texte d'un cycle, prêt à coller dans WhatsApp.

    Les blocs sensibles ne sont écrits que si l'appelant y a droit : le texte ne contient
    jamais une information que son destinataire n'aurait pas le droit de voir dans l'application.
    """
    today = timezone.localdate()
    summary = cycle_summary(cycle)
    currency = getattr(cycle.organization, "currency", "") or ""

    header = f"Cycle « {cycle.name} » — {cycle.coop.name}"
    if cycle.status == Cycle.Status.ACTIVE:
        header += f" — jour {(today - cycle.start_date).days + 1}"
    lines = [
        "*AVIKA — Rapport*",
        header,
        f"Date : {today.isoformat()}",
        "",
        f"Effectif : {summary['current_count']} vivants (départ : {summary['initial_count']})",
        f"Mortalité : {_percent(summary['mortality_rate'])}",
    ]

    if include_finance:
        profit = cycle_profitability(cycle)
        lines += [
            f"Vendus : {profit['birds_sold']}",
            "",
            f"Ventes : {_money(profit['revenue'], currency)}",
            f"Encaissé : {_money(profit['collected'], currency)}",
            f"Reste à encaisser : {_money(profit['receivables'], currency)}",
            f"Coût de production : {_money(profit['production_cost'], currency)}",
        ]
        if include_profits and profit["result"] is not None:
            lines.append(f"Résultat : {_money(profit['result'], currency)}")
            lines.append(f"Marge : {_percent(profit['margin_percent'])}")

    if include_health:
        grouped = reminders(today)
        mine = {key: [t for t in tasks if t.cycle_id == cycle.pk] for key, tasks in grouped.items()}
        if any(mine.values()):
            lines.append("")
            lines.append("Santé :")
            for label, key in (("En retard", "overdue"), ("Aujourd'hui", "today"), ("Demain", "tomorrow")):
                for task in mine[key]:
                    lines.append(f"- {label} : {task.name}")

    return "\n".join(lines)


def whatsapp_link(text):
    """Lien qui ouvre WhatsApp avec le message déjà écrit (l'utilisateur choisit le destinataire)."""
    return "https://wa.me/?text=" + quote(text)
