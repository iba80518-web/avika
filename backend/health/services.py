from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from audit.services import log_action
from farming.models import Cycle
from inventory.models import StockMovement
from inventory.services import InventoryError, record_movement

from .models import HealthTask, HealthTemplateItem

Status = HealthTask.Status


class HealthError(Exception):
    """Règle de santé non respectée ; le message est destiné à l'utilisateur."""


def _check_cycle_open(cycle):
    if cycle.status in (Cycle.Status.CANCELLED, Cycle.Status.COMPLETED):
        raise HealthError("Ce cycle est terminé ou annulé.")


@transaction.atomic
def create_task(*, cycle, name, kind, due_date, product=None, note="", user=None, uuid=None):
    """Planifie une tâche de santé. Renvoie (tâche, créée)."""
    if uuid is not None:
        existing = HealthTask.objects.filter(uuid=uuid).first()
        if existing is not None:
            if (existing.cycle_id, existing.name, existing.due_date) != (cycle.pk, name, due_date):
                raise HealthError("Cet identifiant d'opération a déjà servi pour autre chose.")
            return existing, False

    _check_cycle_open(cycle)
    if due_date < cycle.start_date:
        raise HealthError("La date prévue précède le début du cycle.")
    if product is not None and not product.is_active:
        raise HealthError("Ce produit est désactivé.")

    extra = {"uuid": uuid} if uuid is not None else {}
    task = HealthTask.objects.create(
        cycle=cycle,
        name=name,
        kind=kind,
        due_date=due_date,
        product=product,
        note=note,
        created_by=user,
        **extra,
    )
    return task, True


@transaction.atomic
def schedule_from_template(*, cycle, template, user=None):
    """Crée les tâches d'un calendrier type pour un cycle : date prévue = début du cycle + jour d'âge.

    Une tâche déjà planifiée (même nom, même date) n'est pas recréée : on peut relancer sans doublon.
    Renvoie la liste des tâches créées.
    """
    _check_cycle_open(cycle)
    if not template.is_active:
        raise HealthError("Ce calendrier est désactivé.")

    created = []
    items = (
        HealthTemplateItem.objects.filter(template=template)
        .select_related("product")
        .order_by("day_of_age", "id")
    )
    for item in items:
        due_date = cycle.start_date + timedelta(days=item.day_of_age)
        if HealthTask.objects.filter(cycle=cycle, name=item.name, due_date=due_date).exists():
            continue
        task, _ = create_task(
            cycle=cycle,
            name=item.name,
            kind=item.kind,
            due_date=due_date,
            product=item.product,
            note=item.note,
            user=user,
        )
        created.append(task)
    return created


@transaction.atomic
def complete_task(task, *, done_date, quantity=None, use_stock=False, user=None):
    """Marque une tâche comme réalisée ; peut retirer la quantité utilisée du stock."""
    # Verrouille la tâche : deux personnes ne peuvent pas la valider en même temps.
    locked = HealthTask.objects.select_for_update().get(pk=task.pk)
    if locked.status != Status.PLANNED:
        raise HealthError("Cette tâche n'est plus à faire.")

    cycle = locked.cycle
    if done_date < cycle.start_date:
        raise HealthError("La date précède le début du cycle.")
    if done_date > timezone.localdate():
        raise HealthError("La date de réalisation ne peut pas être dans le futur.")
    if quantity is not None and quantity <= 0:
        raise HealthError("La quantité doit être supérieure à 0.")

    movement = None
    if use_stock:
        if locked.product is None:
            raise HealthError("Cette tâche n'a pas de produit : impossible de retirer du stock.")
        if quantity is None:
            raise HealthError("Indiquez la quantité utilisée pour retirer du stock.")
        try:
            movement, _ = record_movement(
                product=locked.product,
                movement_type=StockMovement.MovementType.EXIT.value,
                quantity=quantity,
                movement_date=done_date,
                cycle=cycle,
                user=user,
                note=f"Tâche de santé {locked.pk} : {locked.name}",
            )
        except InventoryError as error:
            raise HealthError(str(error))

    locked.status = Status.DONE
    locked.done_date = done_date
    locked.quantity = quantity
    locked.stock_movement = movement
    locked.completed_by = user
    locked.save(
        update_fields=["status", "done_date", "quantity", "stock_movement", "completed_by", "updated_at"]
    )
    log_action(
        user=user,
        action="health.completed",
        obj=locked,
        summary=f"{locked.name} réalisée le {done_date}",
        before={"status": Status.PLANNED.value},
        after={"status": Status.DONE.value, "done_date": str(done_date), "stock_used": movement is not None},
    )
    return locked


@transaction.atomic
def cancel_task(task, *, user=None):
    locked = HealthTask.objects.select_for_update().get(pk=task.pk)
    if locked.status != Status.PLANNED:
        raise HealthError("Seule une tâche à faire peut être annulée.")
    locked.status = Status.CANCELLED
    locked.save(update_fields=["status", "updated_at"])
    log_action(
        user=user,
        action="health.cancelled",
        obj=locked,
        summary=f"{locked.name} annulée",
        before={"status": Status.PLANNED.value},
        after={"status": Status.CANCELLED.value},
    )
    return locked


def reminders(today):
    """Tâches à faire, classées : en retard, aujourd'hui, demain (cycles terminés ou annulés exclus)."""
    tasks = (
        HealthTask.objects.filter(status=Status.PLANNED)
        .exclude(cycle__status__in=[Cycle.Status.CANCELLED, Cycle.Status.COMPLETED])
        .select_related("cycle", "product")
        .order_by("due_date", "id")
    )
    tomorrow = today + timedelta(days=1)
    result = {"overdue": [], "today": [], "tomorrow": []}
    for task in tasks:
        if task.due_date < today:
            result["overdue"].append(task)
        elif task.due_date == today:
            result["today"].append(task)
        elif task.due_date == tomorrow:
            result["tomorrow"].append(task)
    return result
