from uuid import uuid4

from django.core.cache import cache
from rest_framework.test import APIClient, APITestCase

from accounts.models import User
from tenants.models import Membership
from tenants.roles import Role

PASSWORD = "Mot-de-passe-solide-2026"
URL = "/api/v1/egg-collections/"
DAY = "2026-10-03"


class EggApiTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.a = self.register("owner-a@test.com", "Exploitation A")
        self.b = self.register("owner-b@test.com", "Exploitation B")
        self.ca = self.auth(self.a)
        self.cb = self.auth(self.b)
        farm = self.create(self.ca, "/api/v1/farms/", {"name": "Site A"})
        layers = self.create(
            self.ca, "/api/v1/coops/",
            {"farm": farm["id"], "name": "Pondoir", "capacity": 2000, "type": "layer"},
        )
        broilers = self.create(
            self.ca, "/api/v1/coops/", {"farm": farm["id"], "name": "Chair", "capacity": 2000}
        )
        self.cycle = self.start(self.ca, layers, "Pondeuses", "layer")
        self.broiler_cycle = self.start(self.ca, broilers, "Chair", "broiler")

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

    def start(self, client, coop, name, kind):
        cycle = self.create(
            client, "/api/v1/cycles/",
            {"coop": coop["id"], "name": name, "type": kind,
             "start_date": "2026-10-01", "initial_count": 1000},
        )
        started = client.post(f"/api/v1/cycles/{cycle['id']}/start/", {}, format="json")
        self.assertEqual(started.status_code, 200, started.content)
        return cycle

    def payload(self, **extra):
        body = {"cycle": self.cycle["id"], "collected_date": DAY, "collected": 300, "broken": 10,
                "uuid": str(uuid4())}
        body.update(extra)
        return body

    # --- tests ---
    def test_01_enregistrer_puis_renvoyer_ne_cree_pas_de_doublon(self):
        body = self.payload()
        first = self.ca.post(URL, body, format="json")
        self.assertEqual(first.status_code, 201, first.content)
        again = self.ca.post(URL, body, format="json")
        self.assertEqual(again.status_code, 200, again.content)
        self.assertEqual(first.json()["id"], again.json()["id"])
        self.assertEqual(self.ca.get(URL).json()["count"], 1)

    def test_02_une_bande_de_poulets_de_chair_est_refusee(self):
        response = self.ca.post(
            URL, self.payload(cycle=self.broiler_cycle["id"]), format="json"
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("chair", response.content.decode())

    def test_03_le_resume_donne_le_stock_et_le_taux_de_ponte(self):
        self.assertEqual(self.ca.post(URL, self.payload(), format="json").status_code, 201)
        self.assertEqual(
            self.ca.post(URL, self.payload(collected=150, broken=5), format="json").status_code, 201
        )
        response = self.ca.get(URL + f"summary/?cycle={self.cycle['id']}")
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual(data["stock"], 435)
        self.assertEqual(len(data["days"]), 1)
        self.assertEqual(data["days"][0]["date"], DAY)
        self.assertEqual(data["days"][0]["collected"], 450)
        self.assertEqual(data["days"][0]["rate"], 45.0)

    def test_04_corriger_un_comptage_met_le_stock_a_jour(self):
        created = self.ca.post(URL, self.payload(), format="json").json()
        response = self.ca.patch(
            f"{URL}{created['id']}/",
            {"collected": 320, "broken": 20, "note": "Recompté"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        summary = self.ca.get(URL + f"summary/?cycle={self.cycle['id']}").json()
        self.assertEqual(summary["stock"], 300)

    def test_05_droits_employe_autorise_veterinaire_et_comptable_refuses(self):
        employee = self.member(self.a, "emp@test.com", Role.EMPLOYEE)
        self.assertEqual(employee.post(URL, self.payload(), format="json").status_code, 201)
        vet = self.member(self.a, "vet@test.com", Role.VET)
        self.assertEqual(vet.get(URL).status_code, 403)
        accountant = self.member(self.a, "compta@test.com", Role.ACCOUNTANT)
        self.assertEqual(accountant.post(URL, self.payload(), format="json").status_code, 403)
        self.assertIn(APIClient().get(URL).status_code, (401, 403))

    def test_06_une_exploitation_ne_voit_pas_celle_dune_autre(self):
        self.assertEqual(self.ca.post(URL, self.payload(), format="json").status_code, 201)
        self.assertEqual(self.cb.get(URL).json()["count"], 0)
        self.assertEqual(self.cb.post(URL, self.payload(), format="json").status_code, 400)
        self.assertEqual(
            self.cb.get(URL + f"summary/?cycle={self.cycle['id']}").status_code, 404
        )

    def test_07_chiffres_impossibles_et_suppression_refuses(self):
        self.assertEqual(
            self.ca.post(URL, self.payload(collected=10, broken=11), format="json").status_code, 400
        )
        self.assertEqual(self.ca.get(URL + "summary/").status_code, 400)
        created = self.ca.post(URL, self.payload(), format="json").json()
        self.assertIn(self.ca.delete(f"{URL}{created['id']}/").status_code, (403, 405))
        self.assertEqual(self.ca.get(f"{URL}{created['id']}/").status_code, 200)
