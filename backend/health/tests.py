from datetime import date, timedelta
from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from accounts.models import User
from audit.models import AuditLog
from farming.models import Coop, Cycle
from inventory.models import Product
from inventory.services import record_movement, stock_snapshot
from tenants.context import organization_context
from tenants.models import Farm, Membership, Organization
from tenants.roles import Role

from .models import HealthTask, HealthTemplate, HealthTemplateItem
from .services import (
    HealthError,
    cancel_task,
    complete_task,
    create_task,
    reminders,
    schedule_from_template,
)

PASSWORD = "Mot-de-passe-solide-2026"
START = date(2026, 10, 1)


class HealthServiceTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Exploitation A")
        self.other = Organization.objects.create(name="Exploitation B")
        self.today = timezone.localdate()
        with organization_context(self.org):
            farm = Farm.objects.create(name="Site")
            coop = Coop.objects.create(farm=farm, name="Poulailler 1", capacity=2000)
            self.cycle = Cycle.objects.create(
                coop=coop, name="Octobre", start_date=START, initial_count=1000,
                status=Cycle.Status.ACTIVE,
            )
            self.vaccine = Product.objects.create(
                name="Vaccin X", product_type=Product.ProductType.VACCINE, base_unit="dose"
            )
            record_movement(
                product=self.vaccine, movement_type="entry", quantity=100,
                movement_date=START, total_cost=50000,
            )
            self.template = HealthTemplate.objects.create(name="Calendrier test")
            HealthTemplateItem.objects.create(
                template=self.template, name="Vaccin X J1", day_of_age=1, product=self.vaccine
            )
            HealthTemplateItem.objects.create(
                template=self.template, name="Rappel J21", day_of_age=21, product=self.vaccine
            )

    def task(self, **kwargs):
        kwargs.setdefault("cycle", self.cycle)
        kwargs.setdefault("name", "Vaccin X J1")
        kwargs.setdefault("kind", "vaccine")
        kwargs.setdefault("due_date", self.today)
        kwargs.setdefault("product", self.vaccine)
        with organization_context(self.org):
            return create_task(**kwargs)

    def test_01_schedule_from_template_computes_dates_without_duplicates(self):
        with organization_context(self.org):
            created = schedule_from_template(cycle=self.cycle, template=self.template)
            self.assertEqual(
                [task.due_date for task in created], [START + timedelta(days=1), START + timedelta(days=21)]
            )
            again = schedule_from_template(cycle=self.cycle, template=self.template)
            self.assertEqual(again, [])
            self.assertEqual(HealthTask.objects.count(), 2)

    def test_02_complete_with_stock_removes_the_quantity_and_links_the_cycle(self):
        task, _ = self.task()
        with organization_context(self.org):
            done = complete_task(task, done_date=self.today, quantity=Decimal("10"), use_stock=True)
            self.assertEqual(done.status, HealthTask.Status.DONE)
            self.assertEqual(done.stock_movement.cycle_id, self.cycle.pk)
            self.assertEqual(stock_snapshot(self.vaccine), (Decimal("90.000"), 45000))

    def test_03_not_enough_stock_leaves_the_task_untouched(self):
        task, _ = self.task()
        with organization_context(self.org):
            with self.assertRaises(HealthError):
                complete_task(task, done_date=self.today, quantity=Decimal("1000"), use_stock=True)
            self.assertEqual(HealthTask.objects.get(pk=task.pk).status, HealthTask.Status.PLANNED)
            self.assertEqual(stock_snapshot(self.vaccine)[0], Decimal("100.000"))

    def test_04_completion_rules(self):
        task, _ = self.task()
        with organization_context(self.org):
            with self.assertRaises(HealthError):  # dans le futur
                complete_task(task, done_date=self.today + timedelta(days=1))
            with self.assertRaises(HealthError):  # avant le cycle
                complete_task(task, done_date=START - timedelta(days=1))
            with self.assertRaises(HealthError):  # stock demandé sans quantité
                complete_task(task, done_date=self.today, use_stock=True)
            complete_task(task, done_date=self.today)
            with self.assertRaises(HealthError):  # déjà réalisée
                complete_task(task, done_date=self.today)
            with self.assertRaises(HealthError):  # on n'annule pas une tâche réalisée
                cancel_task(task)

    def test_05_cancel_then_nothing_else(self):
        task, _ = self.task()
        with organization_context(self.org):
            cancel_task(task)
            with self.assertRaises(HealthError):
                complete_task(task, done_date=self.today)

    def test_06_reminders_are_sorted_into_overdue_today_tomorrow(self):
        self.task(name="En retard", due_date=self.today - timedelta(days=2))
        self.task(name="Aujourd'hui", due_date=self.today)
        self.task(name="Demain", due_date=self.today + timedelta(days=1))
        self.task(name="Plus tard", due_date=self.today + timedelta(days=5))
        with organization_context(self.org):
            grouped = reminders(self.today)
        self.assertEqual([t.name for t in grouped["overdue"]], ["En retard"])
        self.assertEqual([t.name for t in grouped["today"]], ["Aujourd'hui"])
        self.assertEqual([t.name for t in grouped["tomorrow"]], ["Demain"])

    def test_07_finished_cycle_blocks_new_tasks_and_hides_reminders(self):
        self.task(name="Avant la fin")
        with organization_context(self.org):
            self.cycle.status = Cycle.Status.COMPLETED
            self.cycle.save()
            with self.assertRaises(HealthError):
                create_task(
                    cycle=self.cycle, name="Après", kind="other", due_date=self.today
                )
            grouped = reminders(self.today)
        self.assertEqual(grouped["today"], [])

    def test_08_completion_is_audited_and_isolated(self):
        task, _ = self.task()
        with organization_context(self.org):
            complete_task(task, done_date=self.today)
            self.assertEqual(AuditLog.objects.filter(action="health.completed").count(), 1)
        with organization_context(self.other):
            self.assertEqual(HealthTask.objects.count(), 0)
            self.assertEqual(HealthTemplate.objects.count(), 0)


class HealthApiTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.today = timezone.localdate()
        self.a = self.register("owner-a@test.com", "Exploitation A")
        self.b = self.register("owner-b@test.com", "Exploitation B")
        self.ca = self.auth(self.a)
        self.cb = self.auth(self.b)
        farm = self.create(self.ca, "/api/v1/farms/", {"name": "Site A"})
        coop = self.create(
            self.ca, "/api/v1/coops/", {"farm": farm["id"], "name": "P1", "capacity": 1000}
        )
        self.cycle = self.create(
            self.ca,
            "/api/v1/cycles/",
            {"coop": coop["id"], "name": "Octobre", "start_date": "2026-10-01", "initial_count": 1000},
        )
        started = self.ca.post(f"/api/v1/cycles/{self.cycle['id']}/start/", {}, format="json")
        self.assertEqual(started.status_code, 200, started.content)
        self.product = self.create(
            self.ca, "/api/v1/products/",
            {"name": "Vaccin X", "product_type": "vaccine", "base_unit": "dose"},
        )
        self.product_url = f"/api/v1/products/{self.product['id']}/"
        self.create(
            self.ca, self.product_url + "movements/",
            {"movement_type": "entry", "quantity": "100", "movement_date": "2026-10-01",
             "total_cost": 50000},
        )
        self.template = self.create(self.ca, "/api/v1/health-templates/", {"name": "Calendrier test"})
        for name, day in (("Vaccin X J1", 1), ("Rappel J21", 21)):
            self.create(
                self.ca, "/api/v1/health-template-items/",
                {"template": self.template["id"], "name": name, "kind": "vaccine",
                 "day_of_age": day, "product": self.product["id"]},
            )

    # --- outils ---
    def register(self, email, organization_name):
        response = APIClient().post(
            "/api/v1/auth/register/",
            {"full_name": email, "email": email, "password": PASSWORD,
             "organization_name": organization_name},
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

    def member(self, tokens, email, role):
        user = User.objects.create_user(email=email, password=PASSWORD, full_name=email)
        Membership.objects.create(user=user, organization_id=tokens["organization"]["id"], role=role)
        return self.auth(self.login(email))

    def schedule(self, client=None):
        return (client or self.ca).post(
            "/api/v1/health-tasks/schedule/",
            {"cycle": self.cycle["id"], "template": self.template["id"]},
            format="json",
        )

    # --- tests ---
    def test_01_template_shows_its_items_and_schedules_tasks(self):
        template = self.ca.get(f"/api/v1/health-templates/{self.template['id']}/").json()
        self.assertEqual([item["day_of_age"] for item in template["items"]], [1, 21])
        response = self.schedule()
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual([t["due_date"] for t in response.json()], ["2026-10-02", "2026-10-22"])
        again = self.schedule()
        self.assertEqual(again.status_code, 200)
        self.assertEqual(again.json(), [])
        self.assertEqual(self.ca.get("/api/v1/health-tasks/").json()["count"], 2)

    def test_02_complete_with_stock_through_the_api(self):
        task = self.schedule().json()[0]
        url = f"/api/v1/health-tasks/{task['id']}/complete/"
        body = {"done_date": self.today.isoformat(), "quantity": "10", "use_stock": True}
        response = self.ca.post(url, body, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["status"], "done")
        product = self.ca.get(self.product_url).json()
        self.assertEqual(product["stock"], "90.000")
        self.assertEqual(product["stock_value"], 45000)
        self.assertEqual(self.ca.post(url, body, format="json").status_code, 400)  # déjà réalisée

    def test_03_not_enough_stock_is_refused_and_the_task_stays_planned(self):
        task = self.schedule().json()[0]
        body = {"done_date": self.today.isoformat(), "quantity": "1000", "use_stock": True}
        response = self.ca.post(f"/api/v1/health-tasks/{task['id']}/complete/", body, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.ca.get(f"/api/v1/health-tasks/{task['id']}/").json()["status"], "planned")
        self.assertEqual(self.ca.get(self.product_url).json()["stock"], "100.000")

    def test_04_future_date_and_cancel(self):
        task = self.schedule().json()[0]
        tomorrow = (self.today + timedelta(days=1)).isoformat()
        url = f"/api/v1/health-tasks/{task['id']}/"
        self.assertEqual(
            self.ca.post(url + "complete/", {"done_date": tomorrow}, format="json").status_code, 400
        )
        self.assertEqual(self.ca.post(url + "cancel/", {}, format="json").status_code, 200)
        self.assertEqual(
            self.ca.post(
                url + "complete/", {"done_date": self.today.isoformat()}, format="json"
            ).status_code,
            400,
        )

    def test_05_roles(self):
        self.schedule()
        for email, role, expected in (
            ("emp@test.com", Role.EMPLOYEE, 200),
            ("vet@test.com", Role.VET, 200),
            ("compta@test.com", Role.ACCOUNTANT, 403),
            ("obs@test.com", Role.OBSERVER, 403),
        ):
            client = self.member(self.a, email, role)
            self.assertEqual(client.get("/api/v1/health-tasks/").status_code, expected, email)

    def test_06_other_owner_cannot_reach_anything(self):
        task = self.schedule().json()[0]
        self.assertEqual(self.cb.get("/api/v1/health-tasks/").json()["results"], [])
        self.assertEqual(self.cb.get(f"/api/v1/health-tasks/{task['id']}/").status_code, 404)
        self.assertEqual(
            self.cb.post(
                f"/api/v1/health-tasks/{task['id']}/complete/",
                {"done_date": self.today.isoformat()},
                format="json",
            ).status_code,
            404,
        )
        self.assertEqual(self.cb.get("/api/v1/health-templates/").json()["results"], [])
        # il ne peut pas planifier sur notre cycle ni avec notre calendrier
        self.assertEqual(self.schedule(self.cb).status_code, 400)

    def test_07_reminders_endpoint(self):
        self.schedule()  # deux tâches en retard (2 et 22 octobre)
        for name, offset in (("Aujourd'hui", 0), ("Demain", 1)):
            self.create(
                self.ca, "/api/v1/health-tasks/",
                {"cycle": self.cycle["id"], "name": name, "kind": "treatment",
                 "due_date": (self.today + timedelta(days=offset)).isoformat()},
            )
        data = self.ca.get("/api/v1/health-tasks/reminders/").json()
        self.assertEqual(len(data["overdue"]), 2)
        self.assertEqual([t["name"] for t in data["today"]], ["Aujourd'hui"])
        self.assertEqual([t["name"] for t in data["tomorrow"]], ["Demain"])

    def test_08_manual_task_uuid_is_idempotent(self):
        import uuid

        operation = str(uuid.uuid4())
        body = {"uuid": operation, "cycle": self.cycle["id"], "name": "Visite",
                "kind": "other", "due_date": self.today.isoformat()}
        first = self.ca.post("/api/v1/health-tasks/", body, format="json")
        second = self.ca.post("/api/v1/health-tasks/", body, format="json")
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(self.ca.get("/api/v1/health-tasks/").json()["count"], 1)
