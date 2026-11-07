from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from accounts.models import User
from tenants.models import Membership
from tenants.roles import Role

PASSWORD = "Mot-de-passe-solide-2026"


class DashboardApiTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.today = timezone.localdate().isoformat()
        self.a = self.register("owner-a@test.com", "Exploitation A")
        self.b = self.register("owner-b@test.com", "Exploitation B")
        self.ca = self.auth(self.a)
        self.cb = self.auth(self.b)
        farm = self.create(self.ca, "/api/v1/farms/", {"name": "Site A"})
        coop = self.create(
            self.ca, "/api/v1/coops/", {"farm": farm["id"], "name": "Poulailler 1", "capacity": 1000}
        )
        self.cycle = self.create(
            self.ca,
            "/api/v1/cycles/",
            {"coop": coop["id"], "name": "Octobre", "start_date": "2026-10-01", "initial_count": 1000},
        )
        self.cycle_url = f"/api/v1/cycles/{self.cycle['id']}/"
        started = self.ca.post(self.cycle_url + "start/", {}, format="json")
        self.assertEqual(started.status_code, 200, started.content)

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

    def mortality(self, quantity):
        response = self.ca.post(
            self.cycle_url + "events/",
            {"event_type": "mortality", "quantity": quantity, "event_date": self.today},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)

    def fill_business_data(self):
        customer = self.create(self.ca, "/api/v1/customers/", {"name": "Grossiste"})
        self.create(
            self.ca,
            "/api/v1/sales/",
            {"cycle": self.cycle["id"], "sale_date": self.today, "sale_type": "count",
             "quantity": 10, "unit_price": 50000, "customer": customer["id"],
             "paid_amount": 200000},
        )
        self.create(
            self.ca,
            "/api/v1/expenses/",
            {"amount": 70000, "expense_date": self.today, "category": "transport"},
        )
        product = self.create(
            self.ca,
            "/api/v1/products/",
            {"name": "Aliment", "product_type": "feed", "base_unit": "kg",
             "low_stock_threshold": "20"},
        )
        self.create(
            self.ca,
            f"/api/v1/products/{product['id']}/movements/",
            {"movement_type": "entry", "quantity": "10", "movement_date": self.today,
             "total_cost": 1000},
        )

    # --- tests ---
    def test_01_owner_sees_cycles_stock_and_finance(self):
        self.mortality(3)
        self.fill_business_data()
        response = self.ca.get("/api/v1/dashboard/")
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual(data["date"], self.today)
        [cycle] = data["active_cycles"]
        self.assertEqual(cycle["name"], "Octobre")
        self.assertEqual(cycle["coop"], "Poulailler 1")
        self.assertEqual(cycle["current_count"], 1000 - 3 - 10)
        self.assertEqual(cycle["birds_sold"], 10)
        self.assertGreaterEqual(cycle["day_number"], 1)
        self.assertEqual(data["birds_alive"], 987)
        self.assertEqual([p["name"] for p in data["low_stock"]], ["Aliment"])
        finance = data["finance"]
        self.assertEqual(finance["revenue_month"], 500000)
        self.assertEqual(finance["collected_month"], 200000)
        self.assertEqual(finance["expenses_month"], 70000)
        self.assertEqual(finance["receivables_total"], 300000)

    def test_02_employee_sees_stock_but_no_money(self):
        self.fill_business_data()
        data = self.member(self.a, "emp@test.com", Role.EMPLOYEE).get("/api/v1/dashboard/").json()
        self.assertEqual(len(data["active_cycles"]), 1)
        self.assertIsNone(data["finance"])
        self.assertEqual(len(data["low_stock"]), 1)

    def test_03_accountant_sees_money_but_no_stock(self):
        self.fill_business_data()
        data = self.member(self.a, "compta@test.com", Role.ACCOUNTANT).get("/api/v1/dashboard/").json()
        self.assertIsNone(data["low_stock"])
        self.assertEqual(data["finance"]["receivables_total"], 300000)

    def test_04_observer_sees_neither_stock_nor_money(self):
        data = self.member(self.a, "obs@test.com", Role.OBSERVER).get("/api/v1/dashboard/").json()
        self.assertIsNone(data["low_stock"])
        self.assertIsNone(data["finance"])
        self.assertEqual(len(data["active_cycles"]), 1)

    def test_05_vet_has_no_dashboard(self):
        client = self.member(self.a, "vet@test.com", Role.VET)
        self.assertEqual(client.get("/api/v1/dashboard/").status_code, 403)

    def test_06_other_owner_sees_nothing_of_ours(self):
        self.fill_business_data()
        data = self.cb.get("/api/v1/dashboard/").json()
        self.assertEqual(data["active_cycles"], [])
        self.assertEqual(data["birds_alive"], 0)
        self.assertEqual(data["low_stock"], [])
        self.assertEqual(data["finance"]["revenue_month"], 0)
        self.assertEqual(data["finance"]["receivables_total"], 0)

    def test_07_mortality_alert_only_when_above_usual(self):
        self.mortality(3)  # moins que le minimum : pas d'alerte
        self.assertEqual(self.ca.get("/api/v1/dashboard/").json()["mortality_alerts"], [])
        self.mortality(7)  # 10 aujourd'hui, aucun jour précédent : alerte
        alerts = self.ca.get("/api/v1/dashboard/").json()["mortality_alerts"]
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["today"], 10)
        self.assertEqual(alerts[0]["cycle_name"], "Octobre")
        self.assertIn("supérieure à l'habituelle", alerts[0]["message"])
        self.assertNotIn("maladie", alerts[0]["message"].lower())

    def test_08_a_finished_cycle_leaves_the_dashboard(self):
        done = self.ca.post(self.cycle_url + "complete/", {}, format="json")
        self.assertEqual(done.status_code, 200, done.content)
        data = self.ca.get("/api/v1/dashboard/").json()
        self.assertEqual(data["active_cycles"], [])
        self.assertEqual(data["birds_alive"], 0)
