import uuid
from datetime import date
from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient, APITestCase

from accounts.models import User
from farming.models import Coop, Cycle, FlockEvent, ImmutableRecordError
from farming.services import current_count
from tenants.context import organization_context
from tenants.models import Farm, Membership, Organization
from tenants.roles import Role

from .models import Customer, Payment, Sale
from .services import (
    FinanceError,
    cancel_sale,
    cycle_payments_total,
    cycle_sales_total,
    paid_total,
    record_payment,
    record_sale,
    sale_balance,
)

PASSWORD = "Mot-de-passe-solide-2026"
DAY = date(2026, 10, 5)


class SaleServiceTests(TestCase):
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
            self.customer = Customer.objects.create(name="Boucherie Diallo")

    def sell(self, **kwargs):
        kwargs.setdefault("cycle", self.cycle)
        kwargs.setdefault("sale_date", DAY)
        kwargs.setdefault("sale_type", "count")
        kwargs.setdefault("quantity", 10)
        kwargs.setdefault("unit_price", 50000)
        kwargs.setdefault("paid_amount", 500000)
        with organization_context(self.org):
            return record_sale(**kwargs)

    def count(self):
        with organization_context(self.org):
            return current_count(Cycle.objects.get(pk=self.cycle.pk))

    def test_01_count_sale_computes_total_and_removes_birds(self):
        sale, created = self.sell(quantity=10, unit_price=50000, paid_amount=500000)
        self.assertTrue(created)
        self.assertEqual(sale.total_amount, 500000)
        self.assertEqual(self.count(), 990)
        with organization_context(self.org):
            self.assertEqual(paid_total(sale), 500000)
            self.assertEqual(sale_balance(sale), 0)
            self.assertEqual(sale.flock_event.event_type, FlockEvent.EventType.SALE.value)

    def test_02_weight_sale_rounds_to_the_unit(self):
        sale, _ = self.sell(
            sale_type="weight", quantity=1, weight_kg=Decimal("1.5"), unit_price=3333,
            paid_amount=5000,
        )
        self.assertEqual(sale.total_amount, 5000)  # 4999,5 arrondi à 5000
        sale2, _ = self.sell(
            sale_type="weight", quantity=4, weight_kg=Decimal("12.345"), unit_price=10000,
            paid_amount=123450,
        )
        self.assertEqual(sale2.total_amount, 123450)

    def test_03_credit_sale_needs_a_customer_and_keeps_a_balance(self):
        with self.assertRaises(FinanceError):
            self.sell(paid_amount=100000)  # à crédit sans client
        sale, _ = self.sell(customer=self.customer, paid_amount=200000)
        with organization_context(self.org):
            self.assertEqual(sale_balance(sale), 300000)

    def test_04_not_enough_birds_refuses_everything(self):
        with self.assertRaises(FinanceError):
            self.sell(quantity=1001, unit_price=1000, paid_amount=1001000)
        with organization_context(self.org):
            self.assertEqual(Sale.objects.count(), 0)
            self.assertEqual(Payment.objects.count(), 0)
        self.assertEqual(self.count(), 1000)

    def test_05_cycle_must_be_active(self):
        with organization_context(self.org):
            planned = Cycle.objects.create(
                coop=self.cycle.coop, name="Prévu", start_date=date(2026, 10, 1), initial_count=100
            )
        with self.assertRaises(FinanceError):
            self.sell(cycle=planned)

    def test_06_same_uuid_creates_no_duplicate(self):
        operation = uuid.uuid4()
        first, created_first = self.sell(uuid=operation)
        second, created_second = self.sell(uuid=operation)
        self.assertTrue(created_first)
        self.assertFalse(created_second)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(self.count(), 990)  # retiré une seule fois
        with self.assertRaises(FinanceError):
            self.sell(uuid=operation, quantity=99)

    def test_07_invalid_inputs_are_refused(self):
        with self.assertRaises(FinanceError):
            self.sell(sale_type="weight", weight_kg=None)  # poids obligatoire
        with self.assertRaises(FinanceError):
            self.sell(quantity=0)
        with self.assertRaises(FinanceError):
            self.sell(unit_price=0)
        with self.assertRaises(FinanceError):
            self.sell(paid_amount=500001)  # plus que le total
        self.assertEqual(self.count(), 1000)

    def test_08_payments_up_to_the_balance(self):
        sale, _ = self.sell(customer=self.customer, paid_amount=100000)
        with organization_context(self.org):
            record_payment(sale=sale, amount=250000, payment_date=DAY)
            with self.assertRaises(FinanceError):
                record_payment(sale=sale, amount=150001, payment_date=DAY)  # dépasse le reste
            with self.assertRaises(FinanceError):
                record_payment(sale=sale, amount=1, payment_date=date(2026, 10, 1))
            record_payment(sale=sale, amount=150000, payment_date=DAY)
            self.assertEqual(sale_balance(sale), 0)

    def test_09_payment_same_uuid_is_idempotent(self):
        sale, _ = self.sell(customer=self.customer, paid_amount=0)
        operation = uuid.uuid4()
        with organization_context(self.org):
            first, created_first = record_payment(
                sale=sale, amount=1000, payment_date=DAY, uuid=operation
            )
            second, created_second = record_payment(
                sale=sale, amount=1000, payment_date=DAY, uuid=operation
            )
            self.assertTrue(created_first)
            self.assertFalse(created_second)
            self.assertEqual(paid_total(sale), 1000)

    def test_10_cancel_restores_birds_and_blocks_payments(self):
        sale, _ = self.sell(customer=self.customer, paid_amount=0)
        self.assertEqual(self.count(), 990)
        with organization_context(self.org):
            cancelled = cancel_sale(sale, reason="erreur de saisie")
        self.assertEqual(cancelled.status, Sale.Status.CANCELLED)
        self.assertEqual(self.count(), 1000)
        with organization_context(self.org):
            with self.assertRaises(FinanceError):
                record_payment(sale=sale, amount=1, payment_date=DAY)
            with self.assertRaises(FinanceError):
                cancel_sale(sale)  # déjà annulée

    def test_11_sale_with_payments_cannot_be_cancelled(self):
        sale, _ = self.sell(customer=self.customer, paid_amount=1000)
        with organization_context(self.org):
            with self.assertRaises(FinanceError):
                cancel_sale(sale)
        self.assertEqual(self.count(), 990)

    def test_12_payments_are_immutable(self):
        self.sell()
        with organization_context(self.org):
            payment = Payment.objects.get()
            payment.amount = 1
            with self.assertRaises(ImmutableRecordError):
                payment.save()
            with self.assertRaises(ImmutableRecordError):
                payment.delete()

    def test_13_cycle_totals_ignore_cancelled_sales(self):
        self.sell(customer=self.customer, quantity=10, unit_price=50000, paid_amount=200000)
        other, _ = self.sell(customer=self.customer, quantity=5, unit_price=40000, paid_amount=0)
        with organization_context(self.org):
            cancel_sale(other)
            cycle = Cycle.objects.get(pk=self.cycle.pk)
            self.assertEqual(cycle_sales_total(cycle), 500000)
            self.assertEqual(cycle_payments_total(cycle), 200000)


class SaleApiTests(APITestCase):
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
        self.cycle_url = f"/api/v1/cycles/{self.cycle['id']}/"
        started = self.ca.post(self.cycle_url + "start/", {}, format="json")
        self.assertEqual(started.status_code, 200, started.content)
        self.customer = self.create(self.ca, "/api/v1/customers/", {"name": "Boucherie Diallo"})

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

    def sale(self, client, **extra):
        payload = {
            "cycle": self.cycle["id"],
            "sale_date": "2026-10-05",
            "sale_type": "count",
            "quantity": 10,
            "unit_price": 50000,
            "paid_amount": 500000,
            **extra,
        }
        return client.post("/api/v1/sales/", payload, format="json")

    def birds(self):
        return self.ca.get(self.cycle_url + "summary/").json()["current_count"]

    # --- tests ---
    def test_01_total_is_computed_by_the_server(self):
        response = self.sale(self.ca, total_amount=1)  # le client essaie d'imposer un total
        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        self.assertEqual(body["total_amount"], 500000)
        self.assertEqual(body["balance"], 0)
        self.assertEqual(self.birds(), 990)
        summary = self.ca.get(self.cycle_url + "summary/").json()
        self.assertEqual(summary["sold"], 10)

    def test_02_other_owner_cannot_reach_anything(self):
        created = self.sale(self.ca).json()
        self.assertEqual(self.cb.get(f"/api/v1/sales/{created['id']}/").status_code, 404)
        self.assertEqual(self.cb.get("/api/v1/sales/").json()["results"], [])
        self.assertEqual(self.cb.get(f"/api/v1/sales/{created['id']}/payments/").status_code, 404)
        self.assertEqual(
            self.cb.post(f"/api/v1/sales/{created['id']}/cancel/", {}, format="json").status_code,
            404,
        )
        # et il ne peut pas vendre les poulets d'un autre éleveur
        self.assertEqual(self.sale(self.cb).status_code, 400)
        self.assertEqual(self.birds(), 990)

    def test_03_employee_has_no_access_accountant_has(self):
        employee = self.member(self.a, "emp@test.com", Role.EMPLOYEE)
        self.assertEqual(employee.get("/api/v1/sales/").status_code, 403)
        self.assertEqual(self.sale(employee).status_code, 403)
        accountant = self.member(self.a, "compta@test.com", Role.ACCOUNTANT)
        self.assertEqual(self.sale(accountant).status_code, 201)

    def test_04_payments_through_the_api(self):
        created = self.sale(self.ca, customer=self.customer["id"], paid_amount=100000).json()
        url = f"/api/v1/sales/{created['id']}/payments/"
        body = {"amount": 250000, "payment_date": "2026-10-06", "method": "mobile_money"}
        self.assertEqual(self.ca.post(url, body, format="json").status_code, 201)
        too_much = {"amount": 150001, "payment_date": "2026-10-06"}
        self.assertEqual(self.ca.post(url, too_much, format="json").status_code, 400)
        rest = {"amount": 150000, "payment_date": "2026-10-06"}
        self.assertEqual(self.ca.post(url, rest, format="json").status_code, 201)
        self.assertEqual(len(self.ca.get(url).json()), 3)
        self.assertEqual(self.ca.get(f"/api/v1/sales/{created['id']}/").json()["balance"], 0)

    def test_05_cancel_restores_the_birds(self):
        created = self.sale(self.ca, customer=self.customer["id"], paid_amount=0).json()
        self.assertEqual(self.birds(), 990)
        url = f"/api/v1/sales/{created['id']}/cancel/"
        response = self.ca.post(url, {"reason": "erreur"}, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["status"], "cancelled")
        self.assertEqual(self.birds(), 1000)
        self.assertEqual(self.ca.post(url, {}, format="json").status_code, 400)

    def test_06_receivables_list(self):
        created = self.sale(
            self.ca, customer=self.customer["id"], paid_amount=200000
        ).json()
        rows = self.ca.get("/api/v1/sales/receivables/").json()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["customer"], self.customer["id"])
        self.assertEqual(rows[0]["customer_name"], "Boucherie Diallo")
        self.assertEqual(rows[0]["total_due"], 300000)
        self.assertEqual(self.cb.get("/api/v1/sales/receivables/").json(), [])
        pay = {"amount": 300000, "payment_date": "2026-10-06"}
        self.ca.post(f"/api/v1/sales/{created['id']}/payments/", pay, format="json")
        self.assertEqual(self.ca.get("/api/v1/sales/receivables/").json(), [])

    def test_07_same_uuid_is_idempotent(self):
        operation = str(uuid.uuid4())
        first = self.sale(self.ca, uuid=operation)
        second = self.sale(self.ca, uuid=operation)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(self.birds(), 990)
        self.assertEqual(self.ca.get("/api/v1/sales/").json()["count"], 1)

    def test_08_refusals(self):
        self.assertEqual(self.sale(self.ca, quantity=1001, paid_amount=0, customer=self.customer["id"]).status_code, 400)
        self.assertEqual(self.sale(self.ca, paid_amount=100).status_code, 400)  # crédit sans client
        self.assertEqual(self.sale(self.ca, sale_type="weight").status_code, 400)  # sans poids
        created = self.sale(self.ca).json()
        status = self.ca.delete(f"/api/v1/sales/{created['id']}/").status_code
        self.assertIn(status, (403, 405))
        self.assertEqual(self.birds(), 990)
