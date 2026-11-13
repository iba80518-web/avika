from datetime import date, timedelta
from uuid import uuid4

from django.test import TestCase
from django.utils import timezone

from audit.models import AuditLog
from farming.models import Coop, Cycle, FlockEvent
from farming.services import record_event
from tenants.context import organization_context
from tenants.models import Farm, Organization

from .models import EggCollection
from .services import (
    EggError,
    daily_totals,
    egg_stock,
    record_collection,
    update_collection,
)

START = date(2026, 10, 1)


class EggServiceTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Exploitation A")
        self.other = Organization.objects.create(name="Exploitation B")
        self.day = START + timedelta(days=2)
        with organization_context(self.org):
            farm = Farm.objects.create(name="Site")
            layers = Coop.objects.create(
                farm=farm, name="Pondoir 1", capacity=2000, type=Coop.Type.LAYER
            )
            broilers = Coop.objects.create(farm=farm, name="Chair 1", capacity=2000)
            spare = Coop.objects.create(
                farm=farm, name="Pondoir 2", capacity=2000, type=Coop.Type.LAYER
            )
            self.cycle = Cycle.objects.create(
                coop=layers, name="Pondeuses 2026", type=Coop.Type.LAYER,
                start_date=START, initial_count=1000, status=Cycle.Status.ACTIVE,
            )
            self.broiler_cycle = Cycle.objects.create(
                coop=broilers, name="Chair 2026", type=Coop.Type.BROILER,
                start_date=START, initial_count=500, status=Cycle.Status.ACTIVE,
            )
            self.planned_cycle = Cycle.objects.create(
                coop=spare, name="Plus tard", type=Coop.Type.LAYER,
                start_date=START, initial_count=300, status=Cycle.Status.PLANNED,
            )

    def test_un_ramassage_alimente_le_stock_net_des_cassés(self):
        with organization_context(self.org):
            collection, created = record_collection(
                cycle=self.cycle, collected_date=self.day, collected=300, broken=12
            )
            self.assertTrue(created)
            self.assertEqual(egg_stock(self.cycle), 288)
            self.assertEqual(collection.collected, 300)

    def test_un_uuid_deja_recu_ne_cree_pas_de_doublon(self):
        key = uuid4()
        with organization_context(self.org):
            first, created = record_collection(
                cycle=self.cycle, collected_date=self.day, collected=300, uuid=key
            )
            again, created_again = record_collection(
                cycle=self.cycle, collected_date=self.day, collected=300, uuid=key
            )
            self.assertTrue(created)
            self.assertFalse(created_again)
            self.assertEqual(first.pk, again.pk)
            self.assertEqual(EggCollection.objects.count(), 1)
            with self.assertRaises(EggError):
                record_collection(
                    cycle=self.cycle, collected_date=self.day, collected=999, uuid=key
                )

    def test_les_cassés_ne_peuvent_pas_dépasser_les_ramassés(self):
        with organization_context(self.org):
            with self.assertRaises(EggError):
                record_collection(
                    cycle=self.cycle, collected_date=self.day, collected=10, broken=11
                )

    def test_une_bande_de_poulets_de_chair_ne_pond_pas(self):
        with organization_context(self.org):
            with self.assertRaises(EggError):
                record_collection(
                    cycle=self.broiler_cycle, collected_date=self.day, collected=10
                )

    def test_une_bande_qui_nest_pas_en_cours_est_refusée(self):
        with organization_context(self.org):
            with self.assertRaises(EggError):
                record_collection(
                    cycle=self.planned_cycle, collected_date=self.day, collected=10
                )

    def test_les_dates_incohérentes_sont_refusées(self):
        with organization_context(self.org):
            with self.assertRaises(EggError):
                record_collection(
                    cycle=self.cycle, collected_date=START - timedelta(days=1), collected=10
                )
            with self.assertRaises(EggError):
                record_collection(
                    cycle=self.cycle,
                    collected_date=timezone.localdate() + timedelta(days=1),
                    collected=10,
                )

    def test_le_total_du_jour_et_le_taux_de_ponte_suivent_les_pondeuses_vivantes(self):
        with organization_context(self.org):
            record_event(
                cycle=self.cycle,
                event_type=FlockEvent.EventType.MORTALITY.value,
                quantity=100,
                event_date=START + timedelta(days=1),
            )
            record_collection(
                cycle=self.cycle, collected_date=self.day, collected=300, broken=10
            )
            record_collection(
                cycle=self.cycle, collected_date=self.day, collected=150, broken=5
            )
            rows = daily_totals(self.cycle)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["collected"], 450)
            self.assertEqual(rows[0]["broken"], 15)
            self.assertEqual(rows[0]["hens"], 900)
            self.assertEqual(rows[0]["rate"], 50.0)
            self.assertEqual(egg_stock(self.cycle), 435)

    def test_une_correction_met_à_jour_le_stock_et_laisse_une_trace(self):
        with organization_context(self.org):
            collection, _ = record_collection(
                cycle=self.cycle, collected_date=self.day, collected=300, broken=10
            )
            update_collection(collection, collected=320, broken=20, note="Recompté")
            self.assertEqual(egg_stock(self.cycle), 300)
            self.assertEqual(
                AuditLog.objects.filter(action="eggs.collection_updated").count(), 1
            )

    def test_une_exploitation_ne_voit_pas_les_ramassages_dune_autre(self):
        with organization_context(self.org):
            record_collection(cycle=self.cycle, collected_date=self.day, collected=300)
        with organization_context(self.other):
            self.assertEqual(EggCollection.objects.count(), 0)
