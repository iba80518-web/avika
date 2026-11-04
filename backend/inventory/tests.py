import uuid
from datetime import date
from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient, APITestCase

from accounts.models import User
from farming.models import Coop, Cycle, ImmutableRecordError
from tenants.context import CrossTenantError, organization_context
from tenants.models import Farm, Membership, Organization
from tenants.roles import Role

from .models import Product, ProductUnit, StockMovement
from .services import (
    InventoryError,
    cycle_feed_cost,
    is_low,
    record_movement,
    stock_snapshot,
)

PASSWORD = "Mot-de-passe-solide-2026"
DAY = date(2026, 10, 5)


class StockServiceTests(TestCase):
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
            self.feed = Product.objects.create(
                name="Aliment démarrage",
                product_type=Product.ProductType.FEED,
                base_unit="kg",
                low_stock_threshold=Decimal("20"),
            )
            self.bag = ProductUnit.objects.create(
                product=self.feed, name="sac", factor_to_base=Decimal("50")
            )

    def move(self, movement_type, quantity, **kwargs):
        movement_date = kwargs.pop("movement_date", DAY)
        with organization_context(self.org):
            return record_movement(
                product=self.feed,
                movement_type=movement_type,
                quantity=quantity,
                movement_date=movement_date,
                **kwargs,
            )

    def snapshot(self):
        with organization_context(self.org):
            return stock_snapshot(self.feed)

    def test_01_entry_with_unit_conversion(self):
        with organization_context(self.org):
            unit = ProductUnit.objects.get(pk=self.bag.pk)
        movement, created = self.move("entry", 2, unit=unit, total_cost=100000)
        self.assertTrue(created)
        self.assertEqual(movement.quantity, Decimal("100.000"))
        self.assertEqual(self.snapshot(), (Decimal("100.000"), 100000))

    def test_02_weighted_average_cost(self):
        self.move("entry", 100, total_cost=50000)
        self.move("entry", 100, total_cost=70000)
        self.assertEqual(self.snapshot(), (Decimal("200.000"), 120000))
        movement, _ = self.move("exit", 50)
        self.assertEqual(movement.total_cost, 30000)  # 50 kg x 600 GNF
        self.assertEqual(self.snapshot(), (Decimal("150.000"), 90000))

    def test_03_full_exit_leaves_no_rounding_remainder(self):
        self.move("entry", 3, total_cost=100)
        self.move("exit", 1)
        self.move("exit", 1)
        self.move("exit", 1)
        self.assertEqual(self.snapshot(), (Decimal("0.000"), 0))

    def test_04_insufficient_stock_is_refused(self):
        self.move("entry", 10, total_cost=1000)
        with self.assertRaises(InventoryError):
            self.move("exit", 11)
        self.assertEqual(self.snapshot()[0], Decimal("10.000"))

    def test_05_same_uuid_creates_no_duplicate(self):
        operation = uuid.uuid4()
        first, created_first = self.move("entry", 10, total_cost=1000, uuid=operation)
        second, created_second = self.move("entry", 10, total_cost=1000, uuid=operation)
        self.assertTrue(created_first)
        self.assertFalse(created_second)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(self.snapshot()[0], Decimal("10.000"))
        with self.assertRaises(InventoryError):
            self.move("entry", 99, total_cost=1000, uuid=operation)

    def test_06_movements_are_immutable(self):
        movement, _ = self.move("entry", 10, total_cost=1000)
        movement.quantity = Decimal("11")
        with self.assertRaises(ImmutableRecordError):
            movement.save()
        with self.assertRaises(ImmutableRecordError):
            movement.delete()

    def test_07_entry_needs_a_cost(self):
        with self.assertRaises(InventoryError):
            self.move("entry", 10)
        movement, _ = self.move("entry", 10, total_cost=0)  # don gratuit
        self.assertEqual(movement.total_cost, 0)

    def test_08_exit_for_a_cycle_feeds_its_cost(self):
        self.move("entry", 100, total_cost=50000)
        with organization_context(self.org):
            cycle = Cycle.objects.get(pk=self.cycle.pk)
        self.move("exit", 40, cycle=cycle)
        with organization_context(self.org):
            self.assertEqual(cycle_feed_cost(cycle), 20000)

    def test_09_cycle_rules(self):
        self.move("entry", 100, total_cost=50000)
        with organization_context(self.org):
            cycle = Cycle.objects.get(pk=self.cycle.pk)
        with self.assertRaises(InventoryError):  # une entrée ne se rattache pas à un cycle
            self.move("entry", 1, total_cost=10, cycle=cycle)
        with self.assertRaises(InventoryError):  # avant le début du cycle
            self.move("exit", 1, cycle=cycle, movement_date=date(2026, 9, 30))

    def test_10_loss_and_adjustment(self):
        self.move("entry", 100, total_cost=50000)
        self.move("loss", 10)
        self.assertEqual(self.snapshot(), (Decimal("90.000"), 45000))
        self.move("adjustment", -20)
        self.assertEqual(self.snapshot(), (Decimal("70.000"), 35000))
        self.move("adjustment", 5, total_cost=2500)
        self.assertEqual(self.snapshot(), (Decimal("75.000"), 37500))
        with self.assertRaises(InventoryError):
            self.move("adjustment", 0)

    def test_11_low_stock_and_isolation(self):
        self.move("entry", 100, total_cost=50000)
        with organization_context(self.org):
            self.assertFalse(is_low(self.feed))
        self.move("exit", 85)
        with organization_context(self.org):
            self.assertTrue(is_low(self.feed))
        with organization_context(self.other):
            self.assertEqual(Product.objects.count(), 0)
            with self.assertRaises(CrossTenantError):
                StockMovement.objects.create(
                    product=self.feed,
                    movement_type="entry",
                    quantity=Decimal("1"),
                    total_cost=1,
                    movement_date=DAY,
                )


class InventoryApiTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.a = self.register("owner-a@test.com", "Exploitation A")
        self.b = self.register("owner-b@test.com", "Exploitation B")
        self.ca = self.auth(self.a)
        self.cb = self.auth(self.b)
        self.product = self.create(
            self.ca,
            "/api/v1/products/",
            {
                "name": "Aliment démarrage",
                "product_type": "feed",
                "base_unit": "kg",
                "low_stock_threshold": "20",
            },
        )
        self.url = f"/api/v1/products/{self.product['id']}/"
        self.unit = self.create(
            self.ca,
            "/api/v1/product-units/",
            {"product": self.product["id"], "name": "sac", "factor_to_base": "50"},
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

    def move(self, client, movement_type, quantity, **extra):
        payload = {
            "movement_type": movement_type,
            "quantity": quantity,
            "movement_date": "2026-10-05",
            **extra,
        }
        return client.post(self.url + "movements/", payload, format="json")

    # --- tests ---
    def test_01_entry_exit_and_stock(self):
        entry = self.move(self.ca, "entry", "2", unit=self.unit["id"], total_cost=100000)
        self.assertEqual(entry.status_code, 201, entry.content)
        self.assertEqual(entry.json()["base_quantity"], "100.000")
        self.assertEqual(self.move(self.ca, "exit", "40").status_code, 201)
        product = self.ca.get(self.url).json()
        self.assertEqual(product["stock"], "60.000")
        self.assertEqual(product["stock_value"], 60000)
        self.assertEqual(self.ca.get(self.url + "movements/").json()["count"], 2)

    def test_02_other_owner_cannot_reach_anything(self):
        self.assertEqual(self.cb.get(self.url).status_code, 404)
        self.assertEqual(self.cb.get(self.url + "movements/").status_code, 404)
        self.assertEqual(self.move(self.cb, "entry", "1", total_cost=1).status_code, 404)
        self.assertEqual(self.cb.get("/api/v1/products/").json()["results"], [])
        self.assertEqual(self.cb.get("/api/v1/product-units/").json()["results"], [])

    def test_03_cannot_attach_a_unit_to_another_owners_product(self):
        response = self.cb.post(
            "/api/v1/product-units/",
            {"product": self.product["id"], "name": "sac", "factor_to_base": "25"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_04_insufficient_stock_is_refused(self):
        self.move(self.ca, "entry", "10", total_cost=1000)
        self.assertEqual(self.move(self.ca, "exit", "11").status_code, 400)

    def test_05_same_uuid_through_the_api_is_idempotent(self):
        operation = str(uuid.uuid4())
        first = self.move(self.ca, "entry", "10", total_cost=1000, uuid=operation)
        second = self.move(self.ca, "entry", "10", total_cost=1000, uuid=operation)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(self.ca.get(self.url).json()["stock"], "10.000")

    def test_06_employee_can_move_stock_but_not_manage_suppliers(self):
        employee = self.member(self.a, "emp@test.com", Role.EMPLOYEE)
        self.assertEqual(self.move(employee, "entry", "5", total_cost=500).status_code, 201)
        self.assertEqual(employee.get("/api/v1/suppliers/").status_code, 403)
        response = employee.post("/api/v1/suppliers/", {"name": "X"}, format="json")
        self.assertEqual(response.status_code, 403)

    def test_07_observer_and_vet_cannot_touch_stock(self):
        for email, role in (("obs@test.com", Role.OBSERVER), ("vet@test.com", Role.VET)):
            client = self.member(self.a, email, role)
            self.assertEqual(client.get("/api/v1/products/").status_code, 403, email)
            self.assertEqual(self.move(client, "entry", "1", total_cost=1).status_code, 403, email)

    def test_08_low_stock_list_and_no_delete(self):
        self.move(self.ca, "entry", "100", total_cost=50000)
        self.assertEqual(self.ca.get("/api/v1/products/low-stock/").json(), [])
        self.move(self.ca, "exit", "85")
        low = self.ca.get("/api/v1/products/low-stock/").json()
        self.assertEqual([p["id"] for p in low], [self.product["id"]])
        self.assertIn(self.ca.delete(self.url).status_code, (403, 405))
        self.assertEqual(self.cb.get("/api/v1/products/low-stock/").json(), [])
