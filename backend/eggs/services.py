from django.db import transaction
from django.db.models import Case, F, IntegerField, Sum, When
from django.utils import timezone

from audit.services import log_action, snapshot
from farming.models import Coop, Cycle, FlockEvent
from farming.services import NEGATIVE_TYPES

from .models import EggCollection

EGG_FIELDS = ["cycle_id", "collected_date", "collected", "broken", "note"]


class EggError(Exception):
    """Règle de ponte non respectée ; le message est destiné à l'utilisateur."""


def _check_numbers(collected, broken):
    if collected is None or collected < 0:
        raise EggError("Le nombre d'œufs ramassés ne peut pas être négatif.")
    if broken is None or broken < 0 or broken > collected:
        raise EggError(
            "Les œufs cassés ou perdus doivent être compris entre 0 et le nombre d'œufs ramassés."
        )


def _check_cycle(cycle, day):
    if cycle.type == Coop.Type.BROILER:
        raise EggError(
            "Une bande de poulets de chair ne produit pas d'œufs : choisissez une bande de pondeuses."
        )
    if cycle.status != Cycle.Status.ACTIVE:
        raise EggError("Ce cycle n'est pas en cours.")
    if day < cycle.start_date:
        raise EggError("La date précède le début du cycle.")
    if day > timezone.localdate():
        raise EggError("La date du ramassage ne peut pas être dans le futur.")


def egg_stock(cycle):
    """Œufs en stock : ramassés − cassés ou perdus − vendus (ventes valides)."""
    from django.db.models import Sum as _Sum

    from finance.models import Sale  # import tardif : finance lit aussi la ponte

    made = EggCollection.objects.filter(cycle=cycle).aggregate(c=_Sum("collected"), b=_Sum("broken"))
    sold = (
        Sale.objects.filter(cycle=cycle, product=Sale.Product.EGGS, status=Sale.Status.ACTIVE)
        .aggregate(n=_Sum("egg_count"))["n"]
        or 0
    )
    return (made["c"] or 0) - (made["b"] or 0) - sold


def hens_on(cycle, day):
    """Nombre de pondeuses vivantes à la fin d'un jour donné (effectif initial + événements jusque-là)."""
    total = FlockEvent.objects.filter(cycle=cycle, event_date__lte=day).aggregate(
        total=Sum(
            Case(
                When(event_type__in=NEGATIVE_TYPES, then=-F("quantity")),
                default=F("quantity"),
                output_field=IntegerField(),
            )
        )
    )["total"]
    return cycle.initial_count + (total or 0)


def daily_totals(cycle, *, days=30):
    """Totaux par jour (du plus récent au plus ancien) avec le taux de ponte du jour."""
    rows = (
        EggCollection.objects.filter(cycle=cycle)
        .values("collected_date")
        .annotate(total_collected=Sum("collected"), total_broken=Sum("broken"))
        .order_by("-collected_date")[:days]
    )
    result = []
    for row in rows:
        hens = hens_on(cycle, row["collected_date"])
        collected = row["total_collected"] or 0
        result.append(
            {
                "date": row["collected_date"],
                "collected": collected,
                "broken": row["total_broken"] or 0,
                "hens": hens,
                "rate": round(collected / hens * 100, 1) if hens > 0 else None,
            }
        )
    return result


@transaction.atomic
def record_collection(
    *, cycle, collected_date, collected, broken=0, note="", user=None, uuid=None
):
    """Enregistre un ramassage. Renvoie (ramassage, créé). Un uuid déjà reçu ne crée pas de doublon."""
    locked = Cycle.objects.select_for_update().get(pk=cycle.pk)

    if uuid is not None:
        existing = EggCollection.objects.filter(uuid=uuid).first()
        if existing is not None:
            if (
                existing.cycle_id,
                existing.collected_date,
                existing.collected,
                existing.broken,
            ) != (locked.pk, collected_date, collected, broken):
                raise EggError("Cet identifiant d'opération a déjà servi pour autre chose.")
            return existing, False

    _check_numbers(collected, broken)
    _check_cycle(locked, collected_date)

    extra = {"uuid": uuid} if uuid is not None else {}
    collection = EggCollection.objects.create(
        cycle=locked,
        collected_date=collected_date,
        collected=collected,
        broken=broken,
        note=note,
        created_by=user,
        **extra,
    )
    log_action(
        user=user,
        action="eggs.collected",
        obj=collection,
        summary=f"Ramassage de {collected} œufs ({broken} cassés)",
        after=snapshot(collection, EGG_FIELDS),
    )
    return collection, True


@transaction.atomic
def update_collection(collection, *, collected, broken, note="", user=None):
    """Corrige un ramassage (erreur de comptage). Le changement est journalisé."""
    locked = Cycle.objects.select_for_update().get(pk=collection.cycle_id)
    _check_numbers(collected, broken)
    _check_cycle(locked, collection.collected_date)

    before = snapshot(collection, EGG_FIELDS)
    collection.collected = collected
    collection.broken = broken
    collection.note = note
    collection.save(update_fields=["collected", "broken", "note", "updated_at"])
    log_action(
        user=user,
        action="eggs.collection_updated",
        obj=collection,
        summary=f"Ramassage {collection.pk} corrigé",
        before=before,
        after=snapshot(collection, EGG_FIELDS),
    )
    return collection
