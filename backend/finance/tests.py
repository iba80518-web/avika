import uuid
from datetime import date

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient, APITestCase

from accounts.models import User
from farming.models import Coop, Cycle
from inventory.models import Supplier
from tenants.context import CrossTenantError, organization_context
from tenants.models import Farm, Membership, Organization
from tenants.roles import Role

from .models import Customer, Expense
from .services import FinanceError, cycle_expense_total, record_expense

PASSWORD = "Mot-de-passe-solide-2026"
DAY = date(2026, 10, 5)


class ExpenseServiceTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Exploitation A")
        self.other = Organization.objects.create(name="Exploitation B")
        with organization_context(self.org):
            farm = Farm.objects.create(name="Site")
            coop = Coop.objects.create(farm=farm, name="Poulailler 1", capacity=1000)
            self.cycle = Cycle.objects.create(
                coop=coop,
                name="Octobre",
                start_date=date(2026, 10, 1),
                initial_count=1000,
                status=Cycle.Status.ACTIVE,
            )
            self.supplier = Supplier.objects.create(name="Fournisseur 1")

    def spend(self, amount=10000, **kwargs):
        kwargs.setdefault("expense_date", DAY)
        kwargs.setdefault("category", "transport")
        with organization_context(self.org):
            return record_expense(amount=amount, **kwargs)

    def test_01_cycle_total_adds_only_its_own_expenses(self):
        self.spend(10000, cycle=self.cycle)
        self.spend(2500, cycle=self.cycle)
        self.spend(99999)  # charge générale, sans cycle
        with organization_context(self.org):
            self.assertEqual(cycle_expense_total(self.cycle), 12500)

    def test_02_invalid_amount_is_refused(self):
        with self.assertRaises(FinanceError):
            self.spend(0)
        with self.assertRaises(FinanceError):
            self.spend(-5)

    def test_03_same_uuid_creates_no_duplicate(self):
        operation = uuid.uuid4()
        first, created_first = self.spend(5000, uuid=operation)
        second, created_second = self.spend(5000, uuid=operation)
        self.assertTrue(created_first)
        self.assertFalse(created_second)
        self.assertEqual(first.pk, second.pk)
        with self.assertRaises(FinanceError):
            self.spend(9999, uuid=operation)  # même identifiant, autre montant
        with organization_context(self.org):
            self.assertEqual(Expense.objects.count(), 1)

    def test_04_cancelled_cycle_is_refused(self):
        with organization_context(self.org):
            self.cycle.status = Cycle.Status.CANCELLED
            self.cycle.save()
        with self.assertRaises(FinanceError):
            self.spend(1000, cycle=self.cycle)

    def test_05_inactive_supplier_is_refused(self):
        with organization_context(self.org):
            self.supplier.is_active = False
            self.supplier.save()
        with self.assertRaises(FinanceError):
            self.spend(1000, supplier=self.supplier)

    def test_06_expense_before_cycle_start_is_allowed(self):
        expense, created = self.spend(
            300000, cycle=self.cycle, category="chicks", expense_date=date(2026, 9, 28)
        )
        self.assertTrue(created)
        self.assertEqual(expense.cycle_id, self.cycle.pk)

    def test_07_isolation_between_organizations(self):
        self.spend(1000)
        with organization_context(self.other):
            self.assertEqual(Expense.objects.count(), 0)
            with self.assertRaises(CrossTenantError):
                Expense.objects.create(
                    amount=1, expense_date=DAY, category="other", cycle=self.cycle
                )


class FinanceApiTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.a = self.register("owner-a@test.com", "Exploitation A")
        self.b = self.register("owner-b@test.com", "Exploitation B")
        self.ca = self.auth(self.a)
        self.cb = self.auth(self.b)
        farm = self.create(self.ca, "/api/v1/farms/", {"name": "Site A"})
        coop = self.create(
            self.ca,
            "/api/v1/coops/",
            {"farm": farm["id"], "name": "Poulailler 1", "capacity": 1000},
        )
        self.cycle = self.create(
            self.ca,
            "/api/v1/cycles/",
            {
                "coop": coop["id"],
                "name": "Octobre",
                "start_date": "2026-10-01",
                "initial_count": 1000,
            },
        )

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

    def member(self, tokens, email, role):
        user = User.objects.create_user(email=email, password=PASSWORD, full_name=email)
        Membership.objects.create(user=user, organization_id=tokens["organization"]["id"], role=role)
        return self.auth(self.login(email))

    def expense(self, client, amount=10000, **extra):
        payload = {
            "amount": amount,
            "expense_date": "2026-10-05",
            "category": "transport",
            **extra,
        }
        return client.post("/api/v1/expenses/", payload, format="json")

    # --- tests ---
    def test_01_create_list_and_filter(self):
        self.assertEqual(self.expense(self.ca, 10000, cycle=self.cycle["id"]).status_code, 201)
        self.assertEqual(self.expense(self.ca, 500, category="rent").status_code, 201)
        self.assertEqual(self.ca.get("/api/v1/expenses/").json()["count"], 2)
        by_cycle = self.ca.get(f"/api/v1/expenses/?cycle={self.cycle['id']}").json()
        self.assertEqual(by_cycle["count"], 1)
        by_category = self.ca.get("/api/v1/expenses/?category=rent").json()
        self.assertEqual(by_category["count"], 1)

    def test_02_other_owner_cannot_reach_anything(self):
        created = self.expense(self.ca, 10000).json()
        self.assertEqual(self.cb.get(f"/api/v1/expenses/{created['id']}/").status_code, 404)
        self.assertEqual(self.cb.get("/api/v1/expenses/").json()["results"], [])
        self.assertEqual(self.cb.get("/api/v1/customers/").json()["results"], [])

    def test_03_cannot_attach_an_expense_to_another_owners_cycle(self):
        response = self.expense(self.cb, 10000, cycle=self.cycle["id"])
        self.assertEqual(response.status_code, 400)

    def test_04_employee_and_observer_have_no_access(self):
        for email, role in (("emp@test.com", Role.EMPLOYEE), ("obs@test.com", Role.OBSERVER)):
            client = self.member(self.a, email, role)
            self.assertEqual(client.get("/api/v1/expenses/").status_code, 403, email)
            self.assertEqual(self.expense(client, 1).status_code, 403, email)
            self.assertEqual(client.get("/api/v1/customers/").status_code, 403, email)

    def test_05_accountant_can_record_expenses_and_customers(self):
        client = self.member(self.a, "compta@test.com", Role.ACCOUNTANT)
        self.assertEqual(self.expense(client, 7000).status_code, 201)
        response = client.post("/api/v1/customers/", {"name": "Boucherie Diallo"}, format="json")
        self.assertEqual(response.status_code, 201, response.content)

    def test_06_same_uuid_through_the_api_is_idempotent(self):
        operation = str(uuid.uuid4())
        first = self.expense(self.ca, 5000, uuid=operation)
        second = self.expense(self.ca, 5000, uuid=operation)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(self.ca.get("/api/v1/expenses/").json()["count"], 1)

    def test_07_invalid_amount_and_no_delete(self):
        self.assertEqual(self.expense(self.ca, 0).status_code, 400)
        created = self.expense(self.ca, 1000).json()
        status = self.ca.delete(f"/api/v1/expenses/{created['id']}/").status_code
        self.assertIn(status, (403, 405))
        self.assertEqual(self.ca.get("/api/v1/expenses/").json()["count"], 1)

    def test_08_customer_name_is_unique_per_organization(self):
        self.create(self.ca, "/api/v1/customers/", {"name": "Boucherie Diallo"})
        duplicate = self.ca.post("/api/v1/customers/", {"name": "Boucherie Diallo"}, format="json")
        self.assertEqual(duplicate.status_code, 400)
        # Une autre exploitation peut avoir un client du même nom.
        self.create(self.cb, "/api/v1/customers/", {"name": "Boucherie Diallo"})

    def test_09_cancelled_cycle_is_refused(self):
        url = f"/api/v1/cycles/{self.cycle['id']}/"
        self.assertEqual(self.ca.post(url + "cancel/", {}, format="json").status_code, 200)
        response = self.expense(self.ca, 1000, cycle=self.cycle["id"])
        self.assertEqual(response.status_code, 400)
