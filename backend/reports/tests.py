from datetime import timedelta

from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from accounts.models import User
from tenants.models import Membership
from tenants.roles import Role

PASSWORD = "Mot-de-passe-solide-2026"


class ReportApiTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.today = timezone.localdate()
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
        self.url = f"/api/v1/reports/{self.cycle['id']}/whatsapp/"
        self.create(
            self.ca, self.cycle_url + "events/",
            {"event_type": "mortality", "quantity": 3, "event_date": self.today.isoformat()},
        )
        customer = self.create(self.ca, "/api/v1/customers/", {"name": "Grossiste"})
        self.create(
            self.ca, "/api/v1/sales/",
            {"cycle": self.cycle["id"], "sale_date": self.today.isoformat(), "sale_type": "count",
             "quantity": 10, "unit_price": 50000, "customer": customer["id"], "paid_amount": 200000},
        )
        self.create(
            self.ca, "/api/v1/health-tasks/",
            {"cycle": self.cycle["id"], "name": "Rappel vaccin", "kind": "vaccine",
             "due_date": (self.today - timedelta(days=1)).isoformat()},
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
    def test_01_owner_gets_the_full_report(self):
        response = self.ca.get(self.url)
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        text = data["text"]
        self.assertIn("Octobre", text)
        self.assertIn("Poulailler 1", text)
        self.assertIn("987 vivants", text)
        self.assertIn("Vendus : 10", text)
        self.assertIn("Ventes : 500 000", text)
        self.assertIn("Reste à encaisser : 300 000", text)
        self.assertIn("Résultat", text)
        self.assertIn("En retard : Rappel vaccin", text)
        self.assertTrue(data["whatsapp_url"].startswith("https://wa.me/?text="))

    def test_02_employee_gets_no_money(self):
        text = self.member(self.a, "emp@test.com", Role.EMPLOYEE).get(self.url).json()["text"]
        self.assertIn("987 vivants", text)
        self.assertIn("Rappel vaccin", text)
        self.assertNotIn("Ventes", text)
        self.assertNotIn("500 000", text)
        self.assertNotIn("Résultat", text)

    def test_03_observer_gets_neither_money_nor_health(self):
        text = self.member(self.a, "obs@test.com", Role.OBSERVER).get(self.url).json()["text"]
        self.assertIn("987 vivants", text)
        self.assertNotIn("Ventes", text)
        self.assertNotIn("Santé", text)

    def test_04_vet_has_no_report(self):
        self.assertEqual(self.member(self.a, "vet@test.com", Role.VET).get(self.url).status_code, 403)

    def test_05_other_owner_cannot_read_our_cycle(self):
        self.assertEqual(self.cb.get(self.url).status_code, 404)

    def test_06_unknown_cycle_and_anonymous(self):
        self.assertEqual(self.ca.get("/api/v1/reports/999999/whatsapp/").status_code, 404)
        self.assertIn(APIClient().get(self.url).status_code, (401, 403))

    def test_07_pdf_is_a_real_pdf_download(self):
        response = self.ca.get(f"/api/v1/reports/{self.cycle['id']}/pdf/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_08_pdf_follows_the_same_rights(self):
        url = f"/api/v1/reports/{self.cycle['id']}/pdf/"
        self.assertEqual(self.member(self.a, "emp@test.com", Role.EMPLOYEE).get(url).status_code, 200)
        self.assertEqual(self.member(self.a, "vet@test.com", Role.VET).get(url).status_code, 403)
        self.assertEqual(self.cb.get(url).status_code, 404)

    def test_09_pdf_unknown_cycle(self):
        self.assertEqual(self.ca.get("/api/v1/reports/999999/pdf/").status_code, 404)
