from datetime import date

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient, APITestCase

from accounts.models import User
from farming.models import Coop, Cycle
from inventory.models import Product
from inventory.services import record_movement
from tenants.context import organization_context
from tenants.models import Farm, Membership, Organization
from tenants.roles import Role

from .models import Customer
from .profitability import cycle_profitability
from .services import cancel_sale, record_expense, record_sale

PASSWORD = "Mot-de-passe-solide-2026"
DAY = date(2026, 10, 5)


class ProfitabilityServiceTests(TestCase):
    """Reprend l'exemple du cahier des charges : coût 7 500 000, ventes 11 000 000."""

    def setUp(self):
        self.org = Organization.objects.create(name="Exploitation A")
        with organization_context(self.org):
            farm = Farm.objects.create(name="Site")
            coop = Coop.objects.create(farm=farm, name="Poulailler 1", capacity=2000)
            self.cycle = Cycle.objects.create(
                coop=coop,
                name="Octobre",
                start_date=date(2026, 10, 1),
                initial_count=1000,
                status=Cycle.Status.ACTIVE,
            )
            self.customer = Customer.objects.create(name="Grossiste")
            self.feed = Product.objects.create(
                name="Aliment", product_type=Product.ProductType.FEED, base_unit="kg"
            )

    def build_example(self):
        with organization_context(self.org):
            record_expense(amount=3000000, expense_date=DAY, category="chicks", cycle=self.cycle)
            record_expense(amount=500000, expense_date=DAY, category="labor", cycle=self.cycle)
            record_movement(
                product=self.feed, movement_type="entry", quantity=100,
                movement_date=DAY, total_cost=4000000,
            )
            record_movement(
                product=self.feed, movement_type="exit", quantity=100,
                movement_date=DAY, cycle=self.cycle,
            )
            return record_sale(
                cycle=self.cycle, sale_date=DAY, sale_type="count", quantity=200,
                unit_price=55000, customer=self.customer, paid_amount=6000000,
            )

    def profit(self):
        with organization_context(self.org):
            return cycle_profitability(Cycle.objects.get(pk=self.cycle.pk))

    def test_01_the_phase_1_example(self):
        self.build_example()
        data = self.profit()
        self.assertEqual(data["revenue"], 11000000)
        self.assertEqual(data["collected"], 6000000)
        self.assertEqual(data["receivables"], 5000000)
        self.assertEqual(data["expenses"], 3500000)
        self.assertEqual(data["feed_cost"], 4000000)
        self.assertEqual(data["production_cost"], 7500000)
        self.assertEqual(data["result"], 3500000)
        self.assertEqual(data["margin_percent"], 31.82)
        self.assertEqual(data["birds_started"], 1000)
        self.assertEqual(data["birds_sold"], 200)
        self.assertEqual(data["cost_per_bird_sold"], 37500)
        self.assertEqual(data["cost_per_bird_started"], 7500)
        self.assertEqual(data["current_count"], 800)

    def test_02_a_cancelled_sale_does_not_count(self):
        self.build_example()
        with organization_context(self.org):
            extra, _ = record_sale(
                cycle=self.cycle, sale_date=DAY, sale_type="count", quantity=50,
                unit_price=60000, customer=self.customer, paid_amount=0,
            )
            cancel_sale(extra)
        data = self.profit()
        self.assertEqual(data["revenue"], 11000000)
        self.assertEqual(data["birds_sold"], 200)
        self.assertEqual(data["current_count"], 800)

    def test_03_no_sales_means_no_margin_and_a_negative_result(self):
        with organization_context(self.org):
            record_expense(amount=1000, expense_date=DAY, category="other", cycle=self.cycle)
        data = self.profit()
        self.assertEqual(data["revenue"], 0)
        self.assertEqual(data["result"], -1000)
        self.assertIsNone(data["margin_percent"])
        self.assertIsNone(data["cost_per_bird_sold"])
        self.assertEqual(data["cost_per_bird_started"], 1)

    def test_04_general_charges_are_excluded_from_a_cycle(self):
        with organization_context(self.org):
            record_expense(amount=700, expense_date=DAY, category="rent")  # charge générale
        self.assertEqual(self.profit()["expenses"], 0)


class ProfitabilityApiTests(APITestCase):
    def setUp(self):
        cache.clear()
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
        self.url = f"/api/v1/profitability/{self.cycle['id']}/"
        self.ca.post(f"/api/v1/cycles/{self.cycle['id']}/start/", {}, format="json")
        customer = self.create(self.ca, "/api/v1/customers/", {"name": "Grossiste"})
        for amount, category in ((3000000, "chicks"), (500000, "labor")):
            self.create(
                self.ca,
                "/api/v1/expenses/",
                {"amount": amount, "expense_date": "2026-10-05", "category": category,
                 "cycle": self.cycle["id"]},
            )
        product = self.create(
            self.ca, "/api/v1/products/",
            {"name": "Aliment", "product_type": "feed", "base_unit": "kg"},
        )
        movements = f"/api/v1/products/{product['id']}/movements/"
        self.create(
            self.ca, movements,
            {"movement_type": "entry", "quantity": "100", "movement_date": "2026-10-05",
             "total_cost": 4000000},
        )
        self.create(
            self.ca, movements,
            {"movement_type": "exit", "quantity": "100", "movement_date": "2026-10-05",
             "cycle": self.cycle["id"]},
        )
        self.create(
            self.ca,
            "/api/v1/sales/",
            {"cycle": self.cycle["id"], "sale_date": "2026-10-05", "sale_type": "count",
             "quantity": 200, "unit_price": 55000, "customer": customer["id"],
             "paid_amount": 6000000},
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

    # --- tests ---
    def test_01_owner_sees_everything(self):
        response = self.ca.get(self.url)
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual(data["revenue"], 11000000)
        self.assertEqual(data["production_cost"], 7500000)
        self.assertEqual(data["result"], 3500000)
        self.assertEqual(data["margin_percent"], 31.82)
        self.assertEqual(data["receivables"], 5000000)

    def test_02_accountant_sees_finances_but_not_profits(self):
        accountant = self.member(self.a, "compta@test.com", Role.ACCOUNTANT)
        data = accountant.get(self.url).json()
        self.assertEqual(data["revenue"], 11000000)
        self.assertEqual(data["production_cost"], 7500000)
        self.assertIsNone(data["result"])
        self.assertIsNone(data["margin_percent"])

    def test_03_employee_and_manager_have_no_access_by_default(self):
        for email, role in (("emp@test.com", Role.EMPLOYEE), ("chef@test.com", Role.MANAGER)):
            client = self.member(self.a, email, role)
            self.assertEqual(client.get(self.url).status_code, 403, email)

    def test_04_other_owner_cannot_reach_the_cycle(self):
        self.assertEqual(self.cb.get(self.url).status_code, 404)
