"""Crée des données de démonstration pour le compte de développement (jamais en production)."""

from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from farming.models import Coop, Cycle
from farming.services import record_event
from finance.models import Customer, Expense
from finance.services import record_expense, record_sale
from health.models import HealthTask
from health.services import create_task
from inventory.models import Product
from inventory.services import record_movement
from tenants.context import organization_context
from tenants.models import Farm, Membership

DEV_EMAIL = "dev@avika.test"
PREFIX = "Démo"


class Command(BaseCommand):
    help = "Crée une ferme de démonstration (bandes, stock, ventes, rappels) pour dev@avika.test."

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Réservé au développement : DEBUG est désactivé.")
        user = User.objects.filter(email=DEV_EMAIL).first()
        membership = Membership.objects.filter(user=user).select_related("organization").first() if user else None
        if membership is None:
            raise CommandError(f"Compte {DEV_EMAIL} introuvable ou sans exploitation.")
        org = membership.organization
        today = timezone.localdate()
        day = lambda n: today - timedelta(days=n)  # noqa: E731

        with organization_context(org):
            if Cycle.objects.filter(name__startswith=PREFIX).exists():
                self.stdout.write("Données de démonstration : déjà fait.")
                return

            farm = Farm.objects.first() or Farm.objects.create(name="Site principal")
            coop_a = Coop.objects.create(farm=farm, name=f"{PREFIX} Poulailler A", capacity=1500)
            coop_b = Coop.objects.create(farm=farm, name=f"{PREFIX} Poulailler B", capacity=800)

            # Bande A : 35 jours, bien conduite, ventes en cours
            a = Cycle.objects.create(
                coop=coop_a, name=f"{PREFIX} Bande A", start_date=day(35), initial_count=1000,
                unit_price=9000, status=Cycle.Status.ACTIVE, planned_sale_date=today + timedelta(days=7),
            )
            # Bande B : 12 jours, mortalité préoccupante
            b = Cycle.objects.create(
                coop=coop_b, name=f"{PREFIX} Bande B", start_date=day(12), initial_count=500,
                unit_price=9000, status=Cycle.Status.ACTIVE, planned_sale_date=today + timedelta(days=30),
            )

            for n, qty in ((30, 4), (22, 6), (14, 5), (6, 7), (2, 3)):
                record_event(cycle=a, event_type="mortality", quantity=qty, event_date=day(n),
                             cause="Chaleur", user=user)
            for n, qty in ((9, 8), (6, 12), (4, 10), (2, 9), (1, 11)):
                record_event(cycle=b, event_type="mortality", quantity=qty, event_date=day(n),
                             cause="Suspicion de maladie", user=user)

            # Stock : aliment bas, vaccins disponibles
            feed = Product.objects.create(name=f"{PREFIX} Aliment démarrage", product_type="feed",
                                          base_unit="kg", low_stock_threshold=Decimal("100"))
            vaccine = Product.objects.create(name=f"{PREFIX} Vaccin Newcastle", product_type="vaccine",
                                             base_unit="dose", low_stock_threshold=Decimal("200"))
            record_movement(product=feed, movement_type="entry", quantity=Decimal("800"),
                            movement_date=day(20), total_cost=1_600_000, user=user)
            record_movement(product=feed, movement_type="exit", quantity=Decimal("350"),
                            movement_date=day(10), cycle=a, user=user)
            record_movement(product=feed, movement_type="exit", quantity=Decimal("380"),
                            movement_date=day(3), cycle=b, user=user)
            record_movement(product=vaccine, movement_type="entry", quantity=Decimal("1500"),
                            movement_date=day(15), total_cost=300_000, user=user)

            # Dépenses et ventes du mois
            record_expense(amount=4_500_000, expense_date=day(35), category="chicks", cycle=a, user=user,
                           description="Poussins bande A")
            record_expense(amount=900_000, expense_date=today, category="labor", cycle=a, user=user,
                           description="Main-d'œuvre")
            record_expense(amount=250_000, expense_date=day(1), category="transport", cycle=b, user=user)

            client = Customer.objects.create(name="Restaurant Le Kaloum", customer_type="restaurant")
            record_sale(cycle=a, sale_date=day(1), sale_type="count", quantity=120, unit_price=45_000,
                        customer=client, paid_amount=3_000_000, user=user)
            record_sale(cycle=a, sale_date=today, sale_type="count", quantity=60, unit_price=45_000,
                        paid_amount=2_700_000, user=user)

            # Rappels sanitaires : un en retard, un aujourd'hui, un demain
            kind = HealthTask._meta.get_field("kind").default
            create_task(cycle=b, name="Rappel vaccin Newcastle", kind=kind, due_date=day(2),
                        product=vaccine, user=user)
            create_task(cycle=a, name="Vitamines anti-stress", kind=kind, due_date=today, user=user)
            create_task(cycle=b, name="Pesée de contrôle", kind=kind, due_date=today + timedelta(days=1),
                        user=user)

        self.stdout.write(self.style.SUCCESS("Données de démonstration créées."))
