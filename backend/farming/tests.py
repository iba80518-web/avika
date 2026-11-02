import uuid
from datetime import date

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient, APITestCase

from accounts.models import User
from tenants.context import CrossTenantError, organization_context
from tenants.models import Farm, Membership, Organization
from tenants.roles import Role

from .models import Coop, Cycle, ImmutableRecordError
from .services import FarmingError, current_count, cycle_summary, record_event, start_cycle

PASSWORD = "Mot-de-passe-solide-2026"
DAY = date(2026, 10, 5)


class FlockServiceTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Exploitation A")
        self.other = Organization.objects.create(name="Exploitation B")
        with organization_context(self.org):
            self.farm = Farm.objects.create(name="Site")
            self.coop = Coop.objects.create(farm=self.farm, name="Poulailler 1", capacity=1000)
            self.cycle = Cycle.objects.create(
                coop=self.coop,
                name="Octobre",
                start_date=date(2026, 10, 1),
                initial_count=1000,
                status=Cycle.Status.ACTIVE,
            )

    def record(self, event_type, quantity, **kwargs):
        event_date = kwargs.pop("event_date", DAY)
        with organization_context(self.org):
            return record_event(
                cycle=self.cycle,
                event_type=event_type,
                quantity=quantity,
                event_date=event_date,
                **kwargs,
            )

    def count(self):
        with organization_context(self.org):
            return current_count(self.cycle)

    def test_01_count_follows_the_formula(self):
        self.record("entry", 100)
        self.record("mortality", 10)
        self.record("sale", 50)
        self.record("transfer_out", 5)
        self.record("correction", -2)
        self.assertEqual(self.count(), 1000 + 100 - 10 - 50 - 5 - 2)

    def test_02_negative_count_is_refused(self):
        with self.assertRaises(FarmingError):
            self.record("mortality", 1001)
        self.assertEqual(self.count(), 1000)

    def test_03_same_uuid_creates_no_duplicate(self):
        operation = uuid.uuid4()
        first, created_first = self.record("mortality", 10, uuid=operation)
        second, created_second = self.record("mortality", 10, uuid=operation)
        self.assertTrue(created_first)
        self.assertFalse(created_second)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(self.count(), 990)

    def test_04_event_before_cycle_start_is_refused(self):
        with self.assertRaises(FarmingError):
            self.record("mortality", 1, event_date=date(2026, 9, 30))

    def test_05_events_need_an_active_cycle(self):
        with organization_context(self.org):
            coop2 = Coop.objects.create(farm=self.farm, name="Poulailler 2", capacity=500)
            planned = Cycle.objects.create(
                coop=coop2, name="Prévu", start_date=date(2026, 10, 1), initial_count=100
            )
            with self.assertRaises(FarmingError):
                record_event(cycle=planned, event_type="mortality", quantity=1, event_date=DAY)

    def test_06_journal_events_cannot_be_changed_or_deleted(self):
        event, _ = self.record("mortality", 5)
        event.quantity = 6
        with self.assertRaises(ImmutableRecordError):
            event.save()
        with self.assertRaises(ImmutableRecordError):
            event.delete()

    def test_07_mortality_rate(self):
        self.record("mortality", 35)
        with organization_context(self.org):
            self.assertEqual(cycle_summary(self.cycle)["mortality_rate"], 3.5)
        self.record("entry", 500)
        with organization_context(self.org):
            summary = cycle_summary(self.cycle)
        self.assertEqual(summary["mortality_rate"], round(35 * 100 / 1500, 2))
        self.assertEqual(summary["current_count"], 1000 + 500 - 35)

    def test_08_start_rules(self):
        with organization_context(self.org):
            second = Cycle.objects.create(
                coop=self.coop, name="Novembre", start_date=date(2026, 11, 1), initial_count=500
            )
            with self.assertRaises(FarmingError):  # un cycle est déjà en cours ici
                start_cycle(second)

            coop2 = Coop.objects.create(farm=self.farm, name="Poulailler 2", capacity=1000)
            big = Cycle.objects.create(
                coop=coop2, name="Gros", start_date=date(2026, 11, 1), initial_count=1200
            )
            with self.assertRaises(FarmingError):  # au-dessus de la capacité
                start_cycle(big)
            started = start_cycle(big, confirm_over_capacity=True)
            self.assertEqual(started.status, Cycle.Status.ACTIVE)

    def test_09_relations_cannot_cross_organizations(self):
        with organization_context(self.other):
            with self.assertRaises(CrossTenantError):
                Coop.objects.create(farm=self.farm, name="Intrus", capacity=10)


class FarmingApiTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.a = self.register("owner-a@test.com", "Exploitation A")
        self.b = self.register("owner-b@test.com", "Exploitation B")
        self.ca = self.auth(self.a)
        self.cb = self.auth(self.b)
        self.farm = self.create(self.ca, "/api/v1/farms/", {"name": "Site A"})
        self.coop = self.create(
            self.ca,
            "/api/v1/coops/",
            {"farm": self.farm["id"], "name": "Poulailler 1", "capacity": 1000},
        )
        self.cycle = self.create(
            self.ca,
            "/api/v1/cycles/",
            {
                "coop": self.coop["id"],
                "name": "Octobre",
                "start_date": "2026-10-01",
                "initial_count": 1000,
            },
        )
        self.cycle_url = f"/api/v1/cycles/{self.cycle['id']}/"
        started = self.ca.post(self.cycle_url + "start/", {}, format="json")
        self.assertEqual(started.status_code, 200, started.content)

    # --- outils ---
    def register(self, email, organization_name):
        response = APIClient().post(
            "/api/v1/auth/register/",
            {
                "full_name": email,
                "email": email,
                "password": PASSWORD,
                "organization_name": organization_name,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    def login(self, identifier):
        response = APIClient().post(
            "/api/v1/auth/login/", {"identifier": identifier, "password": PASSWORD}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def auth(self, tokens):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer " + tokens["access"])
        return client

    def create(self, client, url, data):
        response = client.post(url, data, format="json")
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    def event(self, client, event_type, quantity, **extra):
        payload = {
            "event_type": event_type,
            "quantity": quantity,
            "event_date": "2026-10-05",
            **extra,
        }
        return client.post(self.cycle_url + "events/", payload, format="json")

    # --- tests ---
    def test_01_full_flow_and_summary(self):
        self.assertEqual(self.event(self.ca, "mortality", 35).status_code, 201)
        summary = self.ca.get(self.cycle_url + "summary/").json()
        self.assertEqual(summary["mortality"], 35)
        self.assertEqual(summary["current_count"], 965)
        self.assertEqual(summary["mortality_rate"], 3.5)
        self.assertEqual(self.ca.get(self.cycle_url).json()["current_count"], 965)
        self.assertEqual(self.ca.get(self.cycle_url + "events/").json()["count"], 1)

    def test_02_other_owner_cannot_reach_anything(self):
        for url in (
            f"/api/v1/coops/{self.coop['id']}/",
            self.cycle_url,
            self.cycle_url + "events/",
            self.cycle_url + "summary/",
        ):
            self.assertEqual(self.cb.get(url).status_code, 404, url)
        self.assertEqual(self.event(self.cb, "mortality", 1).status_code, 404)
        self.assertEqual(self.cb.post(self.cycle_url + "start/", {}, format="json").status_code, 404)
        self.assertEqual(self.cb.get("/api/v1/cycles/").json()["results"], [])
        self.assertEqual(self.cb.get("/api/v1/coops/").json()["results"], [])
        self.assertEqual(self.ca.get(self.cycle_url + "summary/").json()["mortality"], 0)

    def test_03_cannot_create_a_cycle_in_another_owners_coop(self):
        response = self.cb.post(
            "/api/v1/cycles/",
            {
                "coop": self.coop["id"],
                "name": "Intrus",
                "start_date": "2026-10-01",
                "initial_count": 10,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_04_cannot_create_a_coop_on_another_owners_farm(self):
        response = self.cb.post(
            "/api/v1/coops/",
            {"farm": self.farm["id"], "name": "Intrus", "capacity": 10},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_05_employee_can_record_mortality_but_nothing_else(self):
        employee = User.objects.create_user(
            email="emp@test.com", password=PASSWORD, full_name="Employé"
        )
        Membership.objects.create(
            user=employee, organization_id=self.a["organization"]["id"], role=Role.EMPLOYEE
        )
        client = self.auth(self.login("emp@test.com"))
        self.assertEqual(self.event(client, "mortality", 3).status_code, 201)
        self.assertEqual(self.event(client, "entry", 10).status_code, 403)
        self.assertEqual(self.event(client, "correction", -1).status_code, 403)
        self.assertEqual(client.get(self.cycle_url + "summary/").status_code, 200)
        response = client.post(
            "/api/v1/cycles/",
            {"coop": self.coop["id"], "name": "X", "start_date": "2026-10-01", "initial_count": 5},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_06_sales_cannot_be_created_through_this_endpoint(self):
        self.assertEqual(self.event(self.ca, "sale", 10).status_code, 400)

    def test_07_insufficient_stock_is_refused(self):
        self.assertEqual(self.event(self.ca, "mortality", 1001).status_code, 400)

    def test_08_same_uuid_through_the_api_is_idempotent(self):
        operation = str(uuid.uuid4())
        first = self.event(self.ca, "mortality", 5, uuid=operation)
        second = self.event(self.ca, "mortality", 5, uuid=operation)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(self.ca.get(self.cycle_url + "summary/").json()["mortality"], 5)

    def test_09_farm_used_by_a_coop_cannot_be_deleted(self):
        response = self.ca.delete(f"/api/v1/farms/{self.farm['id']}/")
        self.assertEqual(response.status_code, 409)

    def test_10_started_cycle_keeps_its_initial_count(self):
        response = self.ca.patch(self.cycle_url, {"initial_count": 2000}, format="json")
        self.assertEqual(response.status_code, 400)
