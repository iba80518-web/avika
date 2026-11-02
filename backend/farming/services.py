from django.db import transaction
from django.db.models import Case, F, IntegerField, Sum, When
from django.utils import timezone

from .models import Cycle, FlockEvent

EventType = FlockEvent.EventType

# Événements qui font diminuer l'effectif.
NEGATIVE_TYPES = [
    EventType.MORTALITY.value,
    EventType.SALE.value,
    EventType.TRANSFER_OUT.value,
]


class FarmingError(Exception):
    """Règle métier non respectée ; le message est destiné à l'utilisateur."""


def current_count(cycle):
    """Effectif disponible = effectif initial + somme des effets des événements."""
    total = FlockEvent.objects.filter(cycle=cycle).aggregate(
        total=Sum(
            Case(
                When(event_type__in=NEGATIVE_TYPES, then=-F("quantity")),
                default=F("quantity"),
                output_field=IntegerField(),
            )
        )
    )["total"]
    return cycle.initial_count + (total or 0)


def cycle_summary(cycle):
    rows = (
        FlockEvent.objects.filter(cycle=cycle)
        .values("event_type")
        .annotate(total=Sum("quantity"))
    )
    totals = {row["event_type"]: row["total"] for row in rows}

    def get(event_type):
        return totals.get(event_type.value, 0)

    entries = get(EventType.ENTRY)
    transfers_in = get(EventType.TRANSFER_IN)
    mortality = get(EventType.MORTALITY)
    base = cycle.initial_count + entries + transfers_in
    return {
        "initial_count": cycle.initial_count,
        "entries": entries,
        "transfers_in": transfers_in,
        "mortality": mortality,
        "sold": get(EventType.SALE),
        "transfers_out": get(EventType.TRANSFER_OUT),
        "corrections": get(EventType.CORRECTION),
        "current_count": current_count(cycle),
        "mortality_rate": round(mortality * 100 / base, 2) if base else 0.0,
    }


@transaction.atomic
def record_event(
    *, cycle, event_type, quantity, event_date, user=None, cause="", note="", uuid=None
):
    """Ajoute un événement au journal. Renvoie (événement, créé).

    Un uuid déjà reçu ne crée pas de doublon (synchronisation hors connexion).
    """
    # Verrouille le cycle : deux saisies simultanées ne peuvent pas dépasser le stock.
    locked = Cycle.objects.select_for_update().get(pk=cycle.pk)

    if uuid is not None:
        existing = FlockEvent.objects.filter(uuid=uuid).first()
        if existing is not None:
            if (existing.cycle_id, existing.event_type, existing.quantity) != (
                locked.pk,
                event_type,
                quantity,
            ):
                raise FarmingError("Cet identifiant d'opération a déjà servi pour autre chose.")
            return existing, False

    if locked.status != Cycle.Status.ACTIVE:
        raise FarmingError("Ce cycle n'est pas en cours.")
    if event_date < locked.start_date:
        raise FarmingError("La date précède le début du cycle.")
    if quantity == 0 or (event_type != EventType.CORRECTION and quantity < 0):
        raise FarmingError("La quantité est invalide.")

    effect = -quantity if event_type in NEGATIVE_TYPES else quantity
    remaining = current_count(locked)
    if remaining + effect < 0:
        raise FarmingError(f"Effectif insuffisant : il reste {remaining} poulets.")

    extra = {"uuid": uuid} if uuid is not None else {}
    event = FlockEvent.objects.create(
        cycle=locked,
        event_type=event_type,
        quantity=quantity,
        event_date=event_date,
        cause=cause,
        note=note,
        created_by=user,
        **extra,
    )
    return event, True


@transaction.atomic
def start_cycle(cycle, *, confirm_over_capacity=False):
    locked = Cycle.objects.select_for_update().get(pk=cycle.pk)
    if locked.status != Cycle.Status.PLANNED:
        raise FarmingError("Seul un cycle planifié peut être démarré.")
    if Cycle.objects.filter(coop_id=locked.coop_id, status=Cycle.Status.ACTIVE).exists():
        raise FarmingError("Ce poulailler a déjà un cycle en cours.")
    if locked.initial_count > locked.coop.capacity and not confirm_over_capacity:
        raise FarmingError(
            f"L'effectif ({locked.initial_count}) dépasse la capacité du poulailler "
            f"({locked.coop.capacity}). Confirmez avec confirm_over_capacity."
        )
    locked.status = Cycle.Status.ACTIVE
    locked.save(update_fields=["status", "updated_at"])
    return locked


@transaction.atomic
def complete_cycle(cycle):
    locked = Cycle.objects.select_for_update().get(pk=cycle.pk)
    if locked.status != Cycle.Status.ACTIVE:
        raise FarmingError("Seul un cycle en cours peut être terminé.")
    locked.status = Cycle.Status.COMPLETED
    locked.end_date = timezone.localdate()
    locked.save(update_fields=["status", "end_date", "updated_at"])
    return locked


@transaction.atomic
def cancel_cycle(cycle):
    locked = Cycle.objects.select_for_update().get(pk=cycle.pk)
    if locked.status not in (Cycle.Status.PLANNED, Cycle.Status.ACTIVE):
        raise FarmingError("Ce cycle ne peut plus être annulé.")
    locked.status = Cycle.Status.CANCELLED
    locked.save(update_fields=["status", "updated_at"])
    return locked
