from uuid import uuid4

from django.core.cache import cache
from rest_framework.test import APIClient, APITestCase

PASSWORD = "Mot-de-passe-solide-2026"
SALES = "/api/v1/sales/"
EGGS = "/api/v1/egg-collections/"
DAY = "2026-10-03"
SELL_DAY = "2026-10-04"


class EggSaleApiTests(APITestCase):
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

    def auth(self, tokens):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer " + tokens["access"])
        return client

    def create(self, client, url, data):
        response = client.post(url, data, format="json")
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    def start(self, client, coop, name, kind):
        cycle = self.create(
            client, "/api/v1/cycles/",
            {"coop": coop["id"], "name": name, "type": kind,
             "start_date": "2026-10-01", "initial_count": 1000},
        )
        started = client.post(f"/api/v1/cycles/{cycle['id']}/start/", {}, format="json")
        self.assertEqual(started.status_code, 200, started.content)
        return cycle

    def collect(self, collected=300, broken=10):
        response = self.ca.post(
            EGGS,
            {"cycle": self.cycle["id"], "collected_date": DAY, "collected": collected,
             "broken": broken, "uuid": str(uuid4())},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)

    def stock(self):
        response = self.ca.get(EGGS + f"summary/?cycle={self.cycle['id']}")
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()["stock"]

    def sell(self, **extra):
        body = {
            "cycle": self.cycle["id"], "sale_date": SELL_DAY, "sale_type": "count",
            "product": "eggs", "egg_unit": "tray", "price_tier": "retail",
            "quantity": 5, "unit_price": 3000, "paid_amount": 15000, "uuid": str(uuid4()),
        }
        body.update(extra)
        return self.ca.post(SALES, body, format="json")

    # --- tests ---
    def test_01_vente_au_plateau_retire_30_oeufs_par_plateau(self):
        self.collect()  # 290 œufs en stock
        response = self.sell()
        self.assertEqual(response.status_code, 201, response.content)
        data = response.json()
        self.assertEqual(data["product"], "eggs")
        self.assertEqual(data["egg_count"], 150)
        self.assertEqual(data["eggs_per_unit"], 30)
        self.assertEqual(data["total_amount"], 15000)
        self.assertEqual(data["balance"], 0)
        self.assertEqual(self.stock(), 140)

    def test_02_vente_au_carton_par_defaut_360_et_taille_personnalisee(self):
        self.collect(collected=800, broken=0)
        crate = self.sell(egg_unit="crate", quantity=1, unit_price=30000, paid_amount=30000)
        self.assertEqual(crate.status_code, 201, crate.content)
        self.assertEqual(crate.json()["egg_count"], 360)
        custom = self.sell(
            egg_unit="crate", quantity=1, eggs_per_unit=180, unit_price=15000, paid_amount=15000
        )
        self.assertEqual(custom.status_code, 201, custom.content)
        self.assertEqual(custom.json()["egg_count"], 180)
        self.assertEqual(self.stock(), 800 - 360 - 180)

    def test_03_vente_a_lunite_au_tarif_gros(self):
        self.collect()
        response = self.sell(
            egg_unit="egg", price_tier="wholesale", quantity=100, unit_price=90, paid_amount=9000
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["price_tier"], "wholesale")
        self.assertEqual(self.stock(), 190)

    def test_04_stock_insuffisant_est_refuse_et_ne_change_rien(self):
        self.collect()  # 290
        response = self.sell(quantity=10, unit_price=3000, paid_amount=30000)  # 300 œufs
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("Stock d'œufs insuffisant", response.content.decode())
        self.assertEqual(self.stock(), 290)

    def test_05_renvoyer_la_meme_vente_ne_la_compte_pas_deux_fois(self):
        self.collect()
        body_uuid = str(uuid4())
        first = self.sell(uuid=body_uuid)
        again = self.sell(uuid=body_uuid)
        self.assertEqual(first.status_code, 201, first.content)
        self.assertEqual(again.status_code, 200, again.content)
        self.assertEqual(first.json()["id"], again.json()["id"])
        self.assertEqual(self.stock(), 140)

    def test_06_tarif_unite_et_paiement_sont_controles(self):
        self.collect()
        self.assertEqual(self.sell(price_tier="").status_code, 400)
        self.assertEqual(self.sell(egg_unit="").status_code, 400)
        # Non payé en totalité sans client : refusé.
        self.assertEqual(self.sell(paid_amount=0).status_code, 400)
        self.assertEqual(self.stock(), 290)

    def test_07_annuler_une_vente_remet_les_oeufs_en_stock(self):
        self.collect()
        sale = self.sell().json()
        self.assertEqual(self.stock(), 140)
        # La vente a reçu un paiement : on teste donc une vente sans paiement.
        unpaid = self.create(self.ca, "/api/v1/customers/", {"name": "Boutique Madina"})
        sale2 = self.sell(paid_amount=0, customer=unpaid["id"], quantity=2, unit_price=3000)
        self.assertEqual(sale2.status_code, 201, sale2.content)
        self.assertEqual(self.stock(), 80)
        cancelled = self.ca.post(f"{SALES}{sale2.json()['id']}/cancel/", {}, format="json")
        self.assertEqual(cancelled.status_code, 200, cancelled.content)
        self.assertEqual(self.stock(), 140)
        self.assertEqual(sale["product"], "eggs")

    def test_08_les_oeufs_ne_se_vendent_pas_depuis_une_bande_de_chair(self):
        response = self.sell(cycle=self.broiler_cycle["id"])
        self.assertEqual(response.status_code, 400, response.content)

    def test_09_une_exploitation_ne_peut_pas_vendre_les_oeufs_dune_autre(self):
        self.collect()
        body = {
            "cycle": self.cycle["id"], "sale_date": SELL_DAY, "sale_type": "count",
            "product": "eggs", "egg_unit": "tray", "price_tier": "retail", "quantity": 1,
            "unit_price": 3000, "paid_amount": 3000,
        }
        self.assertEqual(self.cb.post(SALES, body, format="json").status_code, 400)
        self.assertEqual(self.stock(), 290)
