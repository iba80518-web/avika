import uuid
from datetime import date

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient, APITestCase

from accounts.models import User
from farming.models import Coop, Cycle, ImmutableRecordError
from finance.models import Customer
from finance.services import cancel_sale, record_expense, record_payment, record_sale
from tenants.context import organization_context
from tenants.models import Farm, Membership, Organization
from tenants.roles import Role

from .models import AuditLog
from .services import log_action, snapshot

PASSWORD = "Mot-de-passe-solide-2026"
DAY = date(2026, 10, 5)


class AuditServiceTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Exploitation A")
        self.other = Organization.objects.create(name="Exploitation B")
        self.user = User.objects.create_user(
            email="u@test.com", password=PASSWORD, full_name="Awa Diallo"
        )
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

    def logs(self, action=None):
        with organization_context(self.org):
            queryset = AuditLog.objects.all()
            if action:
                queryset = queryset.filter(action=action)
            return list(queryset.order_by("id"))

    def sell(self, **kwargs):
        kwargs.setdefault("quantity", 10)
        kwargs.setdefault("paid_amount", 0)
        with organization_context(self.org):
            return record_sale(
                cycle=self.cycle, sale_date=DAY, sale_type="count", unit_price=50000,
                customer=self.customer, user=self.user, **kwargs,
            )

    def test_01_sale_is_logged_with_user_and_values(self):
        sale, _ = self.sell()
        [entry] = self.logs("sale.created")
        self.assertEqual(entry.user_id, self.user.pk)
        self.assertEqual(entry.object_type, "Sale")
        self.assertEqual(entry.object_id, sale.pk)
        self.assertEqual(entry.after["total_amount"], 500000)
        self.assertEqual(entry.after["quantity"], 10)
        self.assertIsNone(entry.before)

    def test_02_payment_and_expense_are_logged(self):
        sale, _ = self.sell()
        with organization_context(self.org):
            record_payment(sale=sale, amount=1000, payment_date=DAY, user=self.user)
            record_expense(
                amount=700, expense_date=DAY, category="labor", cycle=self.cycle, user=self.user
            )
        self.assertEqual(len(self.logs("payment.created")), 1)
        [expense] = self.logs("expense.created")
        self.assertEqual(expense.after["amount"], 700)
        self.assertEqual(expense.after["category"], "labor")

    def test_03_cancel_logs_before_and_after(self):
        sale, _ = self.sell()
        with organization_context(self.org):
            cancel_sale(sale, user=self.user, reason="erreur")
        [entry] = self.logs("sale.cancelled")
        self.assertEqual(entry.before, {"status": "active"})
        self.assertEqual(entry.after, {"status": "cancelled"})
        self.assertIn("erreur", entry.summary)

    def test_04_a_replayed_operation_is_not_logged_twice(self):
        operation = uuid.uuid4()
        self.sell(uuid=operation)
        self.sell(uuid=operation)
        self.assertEqual(len(self.logs("sale.created")), 1)

    def test_05_a_refused_operation_leaves_no_log(self):
        with self.assertRaises(Exception):
            self.sell(quantity=5000)  # plus que l'effectif
        self.assertEqual(self.logs(), [])

    def test_06_the_journal_cannot_be_changed_or_deleted(self):
        self.sell()
        [entry] = self.logs()
        entry.summary = "truqué"
        with self.assertRaises(ImmutableRecordError):
            entry.save()
        with self.assertRaises(ImmutableRecordError):
            entry.delete()

    def test_07_each_organization_sees_only_its_own_journal(self):
        self.sell()
        with organization_context(self.other):
            self.assertEqual(AuditLog.objects.count(), 0)

    def test_08_snapshot_turns_values_into_plain_data(self):
        with organization_context(self.org):
            entry = log_action(
                user=None,
                action="test.action",
                obj=self.cycle,
                after=snapshot(self.cycle, ["start_date", "initial_count", "name"]),
            )
        self.assertEqual(entry.after["start_date"], "2026-10-01")
        self.assertEqual(entry.after["initial_count"], 1000)
        self.assertEqual(entry.after["name"], "Octobre")


class AuditApiTests(APITestCase):
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
        self.ca.post(f"/api/v1/cycles/{self.cycle['id']}/start/", {}, format="json")

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

    def expense(self, client, amount=10000):
        return self.create(
            client,
            "/api/v1/expenses/",
            {"amount": amount, "expense_date": "2026-10-05", "category": "transport"},
        )

    # --- tests ---
    def test_01_owner_reads_the_journal(self):
        self.expense(self.ca, 10000)
        rows = self.ca.get("/api/v1/audit/").json()["results"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["action"], "expense.created")
        self.assertEqual(rows[0]["user_name"], "owner-a@test.com")
        self.assertEqual(rows[0]["after"]["amount"], 10000)

    def test_02_expense_update_records_before_and_after(self):
        created = self.expense(self.ca, 10000)
        response = self.ca.patch(
            f"/api/v1/expenses/{created['id']}/", {"amount": 12000}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.content)
        rows = self.ca.get("/api/v1/audit/?action=expense.updated").json()["results"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["before"]["amount"], 10000)
        self.assertEqual(rows[0]["after"]["amount"], 12000)
        self.assertEqual(rows[0]["object_id"], created["id"])

    def test_03_only_the_owner_can_read_it_by_default(self):
        self.expense(self.ca)
        for email, role in (
            ("compta@test.com", Role.ACCOUNTANT),
            ("chef@test.com", Role.MANAGER),
            ("emp@test.com", Role.EMPLOYEE),
        ):
            client = self.member(self.a, email, role)
            self.assertEqual(client.get("/api/v1/audit/").status_code, 403, email)

    def test_04_other_owner_sees_nothing(self):
        self.expense(self.ca)
        self.assertEqual(self.cb.get("/api/v1/audit/").json()["results"], [])

    def test_05_the_journal_is_read_only(self):
        self.expense(self.ca)
        row = self.ca.get("/api/v1/audit/").json()["results"][0]
        url = f"/api/v1/audit/{row['id']}/"
        self.assertEqual(self.ca.get(url).status_code, 200)
        for method in (self.ca.post, self.ca.put, self.ca.patch, self.ca.delete):
            self.assertIn(method(url, {}, format="json").status_code, (403, 405))
        self.assertIn(self.ca.post("/api/v1/audit/", {}, format="json").status_code, (403, 405))
