from datetime import timedelta

from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from accounts.models import User
from tenants.models import Membership
from tenants.roles import Role

PASSWORD = "Mot-de-passe-solide-2026"


class HealthCostAndDashboardTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.today = timezone.localdate()
        self.a = self.register("owner-a@test.com", "Exploitation A")
        self.ca = self.auth(self.a)
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
        self.vaccine = self.create(
            self.ca, "/api/v1/products/",
            {"name": "Vaccin X", "product_type": "vaccine", "base_unit": "dose"},
        )
        self.create(
            self.ca, f"/api/v1/products/{self.vaccine['id']}/movements/",
            {"movement_type": "entry", "quantity": "100", "movement_date": "2026-10-01",
             "total_cost": 50000},
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

    def task(self, due_offset, product=None):
        body = {"cycle": self.cycle["id"], "name": "Vaccin X", "kind": "vaccine",
                "due_date": (self.today + timedelta(days=due_offset)).isoformat()}
        if product:
            body["product"] = product["id"]
        return self.create(self.ca, "/api/v1/health-tasks/", body)

    # --- tests ---
    def test_01_vaccine_used_is_counted_in_the_cycle_cost(self):
        task = self.task(0, self.vaccine)
        done = self.ca.post(
            f"/api/v1/health-tasks/{task['id']}/complete/",
            {"done_date": self.today.isoformat(), "quantity": "10", "use_stock": True},
            format="json",
        )
        self.assertEqual(done.status_code, 200, done.content)
        data = self.ca.get(f"/api/v1/profitability/{self.cycle['id']}/").json()
        self.assertEqual(data["health_cost"], 5000)  # 10 doses sur 100 achetées 50 000
        self.assertEqual(data["feed_cost"], 0)
        self.assertEqual(data["production_cost"], 5000)
        self.assertEqual(data["result"], -5000)

    def test_02_task_done_without_stock_costs_nothing(self):
        task = self.task(0, self.vaccine)
        self.ca.post(
            f"/api/v1/health-tasks/{task['id']}/complete/",
            {"done_date": self.today.isoformat()},
            format="json",
        )
        data = self.ca.get(f"/api/v1/profitability/{self.cycle['id']}/").json()
        self.assertEqual(data["health_cost"], 0)

    def test_03_dashboard_shows_health_reminders_to_those_who_may_see_them(self):
        self.task(-1)
        self.task(0)
        self.task(1)
        data = self.ca.get("/api/v1/dashboard/").json()["health_reminders"]
        self.assertEqual(len(data["overdue"]), 1)
        self.assertEqual(len(data["today"]), 1)
        self.assertEqual(len(data["tomorrow"]), 1)
        self.assertEqual(data["today"][0]["cycle_name"], "Octobre")
        employee = self.member(self.a, "emp@test.com", Role.EMPLOYEE)
        self.assertEqual(len(employee.get("/api/v1/dashboard/").json()["health_reminders"]["today"]), 1)
        observer = self.member(self.a, "obs@test.com", Role.OBSERVER)
        self.assertIsNone(observer.get("/api/v1/dashboard/").json()["health_reminders"])
