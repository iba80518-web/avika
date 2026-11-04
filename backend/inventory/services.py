from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.db.models import BigIntegerField, Case, DecimalField, ExpressionWrapper, F, Sum, When

from farming.models import Cycle

from .models import Product, StockMovement

MovementType = StockMovement.MovementType
OUTGOING = [MovementType.EXIT.value, MovementType.LOSS.value]
THREE_DECIMALS = Decimal("0.001")
ONE = Decimal("1")

# Effet d'un mouvement sur la quantité : sorties et pertes retirent, le reste ajoute
# (une correction négative est déjà stockée avec une quantité négative).
QUANTITY_EFFECT = Case(
    When(
        movement_type__in=OUTGOING,
        then=ExpressionWrapper(
            -F("quantity"), output_field=DecimalField(max_digits=14, decimal_places=3)
        ),
    ),
    default=F("quantity"),
    output_field=DecimalField(max_digits=14, decimal_places=3),
)

# Effet d'un mouvement sur la valeur du stock.
VALUE_EFFECT = Case(
    When(movement_type__in=OUTGOING, then=-F("total_cost")),
    When(movement_type=MovementType.ADJUSTMENT.value, quantity__lt=0, then=-F("total_cost")),
    default=F("total_cost"),
    output_field=BigIntegerField(),
)


class InventoryError(Exception):
    """Règle de stock non respectée ; le message est destiné à l'utilisateur."""


def stock_snapshot(product):
    """Renvoie (quantité en stock, valeur du stock) calculées sur les mouvements."""
    totals = StockMovement.objects.filter(product=product).aggregate(
        qty=Sum(QUANTITY_EFFECT), val=Sum(VALUE_EFFECT)
    )
    return totals["qty"] or Decimal("0"), totals["val"] or 0


def is_low(product, snapshot=None):
    quantity, _ = snapshot or stock_snapshot(product)
    return product.low_stock_threshold > 0 and quantity <= product.low_stock_threshold


def cycle_feed_cost(cycle):
    """Coût de l'aliment consommé par un cycle (somme des sorties d'aliment)."""
    total = StockMovement.objects.filter(
        cycle=cycle,
        movement_type=MovementType.EXIT.value,
        product__product_type=Product.ProductType.FEED,
    ).aggregate(total=Sum("total_cost"))["total"]
    return total or 0


def _share_of_value(value, quantity, stock):
    """Part de la valeur correspondant à `quantity` sur `stock`, arrondie à l'unité."""
    if stock <= 0:
        return 0
    return int((Decimal(value) * quantity / stock).quantize(ONE, rounding=ROUND_HALF_UP))


def _outgoing_cost(quantity, stock, value):
    # Quand on sort tout le stock, on sort toute la valeur : pas de reste d'arrondi.
    return value if quantity == stock else _share_of_value(value, quantity, stock)


@transaction.atomic
def record_movement(
    *,
    product,
    movement_type,
    quantity,
    movement_date,
    unit=None,
    total_cost=None,
    cycle=None,
    user=None,
    note="",
    uuid=None,
):
    """Ajoute un mouvement de stock. Renvoie (mouvement, créé).

    `quantity` est exprimée dans `unit` (ou dans l'unité de base si `unit` est absent).
    Un uuid déjà reçu ne crée pas de doublon (synchronisation hors connexion).
    """
    quantity = Decimal(str(quantity))
    factor = Decimal(unit.factor_to_base) if unit is not None else ONE
    base_quantity = (quantity * factor).quantize(THREE_DECIMALS, rounding=ROUND_HALF_UP)

    # Verrouille le produit : deux saisies simultanées ne peuvent pas dépasser le stock.
    locked = Product.objects.select_for_update().get(pk=product.pk)

    if unit is not None and unit.product_id != locked.pk:
        raise InventoryError("Cette unité n'appartient pas à ce produit.")

    if uuid is not None:
        existing = StockMovement.objects.filter(uuid=uuid).first()
        if existing is not None:
            if (existing.product_id, existing.movement_type, abs(existing.quantity)) != (
                locked.pk,
                movement_type,
                abs(base_quantity),
            ):
                raise InventoryError("Cet identifiant d'opération a déjà servi pour autre chose.")
            return existing, False

    if not locked.is_active:
        raise InventoryError("Ce produit est désactivé.")
    if base_quantity == 0:
        raise InventoryError("La quantité est invalide.")
    if movement_type != MovementType.ADJUSTMENT and base_quantity < 0:
        raise InventoryError("La quantité doit être positive.")

    if cycle is not None:
        if movement_type != MovementType.EXIT:
            raise InventoryError("Seule une sortie peut être rattachée à un cycle.")
        if cycle.status != Cycle.Status.ACTIVE:
            raise InventoryError("Ce cycle n'est pas en cours.")
        if movement_date < cycle.start_date:
            raise InventoryError("La date précède le début du cycle.")

    stock, value = stock_snapshot(locked)

    if movement_type == MovementType.ENTRY:
        if total_cost is None or total_cost < 0:
            raise InventoryError("Le coût total de l'entrée est obligatoire (0 si gratuit).")
        cost = total_cost
    elif movement_type in OUTGOING or (
        movement_type == MovementType.ADJUSTMENT and base_quantity < 0
    ):
        leaving = abs(base_quantity)
        if leaving > stock:
            raise InventoryError(f"Stock insuffisant : il reste {stock} {locked.base_unit}.")
        cost = _outgoing_cost(leaving, stock, value)
    elif movement_type == MovementType.ADJUSTMENT:
        if total_cost is not None:
            cost = total_cost
        else:
            cost = _share_of_value(value, base_quantity, stock)
    else:
        raise InventoryError("Type de mouvement inconnu.")

    extra = {"uuid": uuid} if uuid is not None else {}
    movement = StockMovement.objects.create(
        product=locked,
        movement_type=movement_type,
        quantity=base_quantity,
        total_cost=cost,
        movement_date=movement_date,
        cycle=cycle,
        note=note,
        created_by=user,
        **extra,
    )
    return movement, True
