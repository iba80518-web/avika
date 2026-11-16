import io
import shutil
import tempfile
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from types import SimpleNamespace as NS
from uuid import uuid4

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import override_settings
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient, APITestCase

from finance.models import Payment, Sale
from finance.services import cancel_sale, record_payment
from tenants.context import reset_organization, set_organization
from tenants.models import Membership

from .logo import logo_file
from .models import Document, DocumentSettings
from .services import _lines

PASSWORD = "Mot-de-passe-solide-2026"
SETTINGS = "/api/v1/document-settings/"
LOGO = "/api/v1/document-settings/logo/"
LOGO_FILE = "/api/v1/document-settings/logo/file/"
DOCS = "/api/v1/documents/"
SALES = "/api/v1/sales/"
SELL_DAY = "2026-10-04"


def image_bytes(fmt="PNG", color=(30, 120, 200), size=(400, 200)):
    out = io.BytesIO()
    Image.new("RGB", size, color).save(out, fmt)
    return out.getvalue()


def rows(response):
    data = response.json()
    return data["results"] if isinstance(data, dict) and "results" in data else data


class DocumentApiTests(APITestCase):
    def setUp(self):
        cache.clear()
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        override = override_settings(PHOTOS_ROOT=Path(tmp))
        override.enable()
        self.addCleanup(override.disable)

        self.year = timezone.localdate().year
        self.a = self.register("owner-a@test.com", "Exploitation A")
        self.b = self.register("owner-b@test.com", "Exploitation B")
        self.ca = self.auth(self.a)
        self.cb = self.auth(self.b)
        self.cycle_a = self.start(self.ca, "Site A")
        self.cycle_b = self.start(self.cb, "Site B")

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

    def start(self, client, farm_name):
        farm = self.create(client, "/api/v1/farms/", {"name": farm_name})
        coop = self.create(
            client, "/api/v1/coops/", {"farm": farm["id"], "name": "Chair", "capacity": 2000}
        )
        cycle = self.create(
            client, "/api/v1/cycles/",
            {"coop": coop["id"], "name": "Bande " + farm_name, "type": "broiler",
             "start_date": "2026-10-01", "initial_count": 1000},
        )
        started = client.post(f"/api/v1/cycles/{cycle['id']}/start/", {}, format="json")
        self.assertEqual(started.status_code, 200, started.content)
        return cycle

    def sell(self, client, cycle, **extra):
        body = {
            "cycle": cycle["id"], "sale_date": SELL_DAY, "sale_type": "count",
            "quantity": 10, "unit_price": 5000, "paid_amount": 50000, "uuid": str(uuid4()),
        }
        body.update(extra)
        response = client.post(SALES, body, format="json")
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    def issue(self, client, kind, **ids):
        return client.post(DOCS, {"kind": kind, **ids}, format="json")

    def organization_of(self, sale_id):
        return Sale.unscoped.get(pk=sale_id).organization_id

    @contextmanager
    def org(self, organization_id):
        token = set_organization(organization_id)
        try:
            yield
        finally:
            reset_organization(token)

    def upload(self, client, data, name="logo.png", mime="image/png"):
        return client.post(
            LOGO, {"image": SimpleUploadedFile(name, data, content_type=mime)}, format="multipart"
        )

    # --- paramètres ---
    def test_01_settings_defaults_and_update(self):
        data = self.ca.get(SETTINGS).json()
        self.assertFalse(data["has_logo"])
        self.assertIsNone(data["logo_url"])
        self.assertEqual(data["defaults"]["name"], "Exploitation A")
        self.assertEqual(data["invoice_prefix"], "FAC")
        self.assertEqual(data["receipt_prefix"], "REC")

        changed = self.ca.patch(
            SETTINGS,
            {"business_name": "Ferme du Soleil", "accent_color": "#B22222", "invoice_prefix": "fac2",
             "tax_id": "NIF-9", "footer_text": "Merci !"},
            format="json",
        )
        self.assertEqual(changed.status_code, 200, changed.content)
        self.assertEqual(changed.json()["invoice_prefix"], "FAC2")
        self.assertEqual(changed.json()["business_name"], "Ferme du Soleil")
        self.assertEqual(self.ca.get(SETTINGS).json()["accent_color"], "#B22222")

    def test_02_settings_validation(self):
        for body in ({"accent_color": "vert"}, {"invoice_prefix": "fac-1"}, {"email": "pas-un-mail"},
                     {"receipt_prefix": ""}):
            response = self.ca.patch(SETTINGS, body, format="json")
            self.assertEqual(response.status_code, 400, (body, response.content))
        self.assertEqual(self.ca.get(SETTINGS).json()["accent_color"], "#1F7A4D")

    # --- numérotation et émission ---
    def test_03_invoice_numbering_and_idempotence(self):
        s1 = self.sell(self.ca, self.cycle_a)
        s2 = self.sell(self.ca, self.cycle_a)
        first = self.issue(self.ca, "invoice", sale=s1["id"])
        self.assertEqual(first.status_code, 201, first.content)
        self.assertEqual(first.json()["number"], f"FAC-{self.year}-0001")
        again = self.issue(self.ca, "invoice", sale=s1["id"])
        self.assertEqual(again.status_code, 200)
        self.assertEqual(again.json()["id"], first.json()["id"])
        second = self.issue(self.ca, "invoice", sale=s2["id"])
        self.assertEqual(second.status_code, 201)
        self.assertEqual(second.json()["number"], f"FAC-{self.year}-0002")
        self.assertEqual(len(rows(self.ca.get(DOCS))), 2)
        self.assertEqual(len(rows(self.ca.get(DOCS + f"?sale={s1['id']}"))), 1)
        self.assertEqual(first.json()["content"]["balance"], 0)

    def test_04_receipts_cumulative_and_frozen(self):
        customer = self.create(self.ca, "/api/v1/customers/", {"name": "Mamadou Diallo", "phone": "622112233"})
        sale = self.sell(self.ca, self.cycle_a, customer=customer["id"], paid_amount=20000)
        first_payment = Payment.unscoped.get(sale_id=sale["id"])
        r1 = self.issue(self.ca, "receipt", payment=first_payment.pk)
        self.assertEqual(r1.status_code, 201, r1.content)
        self.assertEqual(r1.json()["number"], f"REC-{self.year}-0001")
        self.assertEqual(r1.json()["content"]["payment"]["amount"], 20000)
        self.assertEqual((r1.json()["content"]["paid"], r1.json()["content"]["balance"]), (20000, 30000))
        self.assertEqual(r1.json()["customer_name"], "Mamadou Diallo")

        with self.org(self.organization_of(sale["id"])):
            second_payment, _ = record_payment(
                sale=Sale.objects.get(pk=sale["id"]), amount=10000, payment_date=date(2026, 10, 5)
            )
        r2 = self.issue(self.ca, "receipt", payment=second_payment.pk)
        self.assertEqual(r2.status_code, 201)
        self.assertEqual((r2.json()["content"]["paid"], r2.json()["content"]["balance"]), (30000, 20000))
        # Le premier reçu ne change pas quand un paiement s'ajoute.
        frozen = self.ca.get(DOCS + f"{r1.json()['id']}/").json()
        self.assertEqual((frozen["content"]["paid"], frozen["content"]["balance"]), (20000, 30000))
        self.assertEqual(self.issue(self.ca, "receipt", payment=first_payment.pk).status_code, 200)

        invoice = self.issue(self.ca, "invoice", sale=sale["id"]).json()
        self.assertEqual((invoice["content"]["paid"], invoice["content"]["balance"]), (30000, 20000))
        with self.org(self.organization_of(sale["id"])):
            record_payment(
                sale=Sale.objects.get(pk=sale["id"]), amount=5000, payment_date=date(2026, 10, 6)
            )
        again = self.ca.get(DOCS + f"{invoice['id']}/").json()
        self.assertEqual(again["content"]["paid"], 30000)

    def test_05_issuer_snapshot_is_frozen(self):
        s1 = self.sell(self.ca, self.cycle_a)
        s2 = self.sell(self.ca, self.cycle_a)
        old = self.issue(self.ca, "invoice", sale=s1["id"]).json()
        self.assertEqual(old["content"]["issuer"]["name"], "Exploitation A")
        self.ca.patch(SETTINGS, {"business_name": "Nouvelle Ferme", "address": "Rue Neuve"}, format="json")
        kept = self.ca.get(DOCS + f"{old['id']}/").json()
        self.assertEqual(kept["content"]["issuer"]["name"], "Exploitation A")
        new = self.issue(self.ca, "invoice", sale=s2["id"]).json()
        self.assertEqual(new["content"]["issuer"]["name"], "Nouvelle Ferme")
        self.assertEqual(new["content"]["issuer"]["address"], "Rue Neuve")

    def test_06_customer_name_rules(self):
        walk_in = self.sell(self.ca, self.cycle_a)
        named = self.issue(self.ca, "invoice", sale=walk_in["id"], customer_name="  Fatou Barry ")
        self.assertEqual(named.json()["customer_name"], "Fatou Barry")

        anonymous = self.sell(self.ca, self.cycle_a)
        self.assertEqual(self.issue(self.ca, "invoice", sale=anonymous["id"]).json()["customer_name"], "")

        customer = self.create(self.ca, "/api/v1/customers/", {"name": "Mamadou Diallo", "phone": "622112233"})
        registered = self.sell(self.ca, self.cycle_a, customer=customer["id"], paid_amount=10000)
        document = self.issue(self.ca, "invoice", sale=registered["id"], customer_name="Autre nom")
        self.assertEqual(document.json()["customer_name"], "Mamadou Diallo")

    def test_07_cancelled_sale(self):
        # Une vente déjà payée ne peut pas être annulée : seule une vente à crédit sans paiement le peut.
        customer = self.create(self.ca, "/api/v1/customers/", {"name": "Mamadou Diallo", "phone": "622112233"})
        sale = self.sell(self.ca, self.cycle_a, customer=customer["id"], paid_amount=0)
        other = self.sell(self.ca, self.cycle_a, customer=customer["id"], paid_amount=0)
        invoice = self.issue(self.ca, "invoice", sale=sale["id"]).json()
        self.assertEqual((invoice["content"]["paid"], invoice["content"]["balance"]), (0, 50000))
        self.assertEqual(invoice["sale_status"], "active")
        with self.org(self.organization_of(sale["id"])):
            cancel_sale(Sale.objects.get(pk=sale["id"]), reason="test")
            cancel_sale(Sale.objects.get(pk=other["id"]), reason="test")
        # Le document déjà émis reste consultable et téléchargeable, marqué comme annulé.
        self.assertEqual(self.ca.get(DOCS + f"{invoice['id']}/").json()["sale_status"], "cancelled")
        self.assertEqual(self.ca.get(DOCS + f"{invoice['id']}/pdf/").status_code, 200)
        # Aucun nouveau document pour une vente annulée.
        refused = self.issue(self.ca, "invoice", sale=other["id"])
        self.assertEqual(refused.status_code, 400)
        self.assertIn("annulée", refused.json()["detail"])

    def test_08_pdf_download(self):
        sale = self.sell(self.ca, self.cycle_a)
        document = self.issue(self.ca, "invoice", sale=sale["id"], customer_name="Awa Sow").json()
        response = self.ca.get(document["pdf_url"])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertIn(document["number"], response["Content-Disposition"])

    def test_09_isolation(self):
        sale_a = self.sell(self.ca, self.cycle_a)
        doc_a = self.issue(self.ca, "invoice", sale=sale_a["id"]).json()
        self.assertEqual(rows(self.cb.get(DOCS)), [])
        self.assertEqual(self.cb.get(DOCS + f"{doc_a['id']}/").status_code, 404)
        self.assertEqual(self.cb.get(DOCS + f"{doc_a['id']}/pdf/").status_code, 404)
        self.assertEqual(self.issue(self.cb, "invoice", sale=sale_a["id"]).status_code, 400)
        sale_b = self.sell(self.cb, self.cycle_b)
        mine = self.issue(self.cb, "invoice", sale=sale_b["id"]).json()
        self.assertEqual(mine["number"], f"FAC-{self.year}-0001")
        self.cb.patch(SETTINGS, {"business_name": "Ferme B"}, format="json")
        self.assertEqual(self.ca.get(SETTINGS).json()["business_name"], "")
        self.assertEqual(self.cb.get(LOGO_FILE).status_code, 404)

    def test_10_roles(self):
        sale = self.sell(self.ca, self.cycle_a)
        Membership.objects.filter(user__email="owner-a@test.com").update(role="accountant")
        self.assertEqual(self.ca.get(DOCS).status_code, 200)
        self.assertEqual(self.issue(self.ca, "invoice", sale=sale["id"]).status_code, 201)
        self.assertEqual(self.ca.get(SETTINGS).status_code, 403)
        self.assertEqual(self.ca.patch(SETTINGS, {"business_name": "X"}, format="json").status_code, 403)
        self.assertEqual(self.upload(self.ca, image_bytes()).status_code, 403)
        for role in ("observer", "employee"):
            Membership.objects.filter(user__email="owner-a@test.com").update(role=role)
            self.assertEqual(self.ca.get(DOCS).status_code, 403, role)
            self.assertEqual(self.issue(self.ca, "invoice", sale=sale["id"]).status_code, 403, role)

    # --- logo ---
    def test_11_logo(self):
        organization = self.organization_of(self.sell(self.ca, self.cycle_a)["id"])
        sale = self.sell(self.ca, self.cycle_a)

        for data, name, mime in (
            (b"pas une image", "logo.png", "image/png"),
            (image_bytes("GIF"), "logo.gif", "image/gif"),
        ):
            self.assertEqual(self.upload(self.ca, data, name, mime).status_code, 400, name)
        self.assertEqual(self.ca.post(LOGO, {}, format="multipart").status_code, 400)

        first = self.upload(self.ca, image_bytes(color=(200, 0, 0)))
        self.assertEqual(first.status_code, 200, first.content)
        self.assertTrue(first.json()["has_logo"])
        shown = self.ca.get(LOGO_FILE)
        self.assertEqual(shown.status_code, 200)
        self.assertEqual(shown["Content-Type"], "image/png")
        self.assertEqual(shown["Cache-Control"], "private, no-store")
        self.assertTrue(b"".join(shown.streaming_content).startswith(b"\x89PNG"))
        path1 = DocumentSettings.unscoped.get(organization_id=organization).logo_path

        self.assertEqual(self.upload(self.ca, image_bytes(color=(0, 0, 200))).status_code, 200)
        path2 = DocumentSettings.unscoped.get(organization_id=organization).logo_path
        self.assertNotEqual(path1, path2)
        self.assertTrue(logo_file(path1).is_file())  # l'ancien fichier est gardé

        document = self.issue(self.ca, "invoice", sale=sale["id"]).json()
        self.assertEqual(document["content"]["issuer"]["logo_path"], path2)
        self.assertEqual(self.ca.get(document["pdf_url"]).status_code, 200)

        removed = self.ca.delete(LOGO)
        self.assertEqual(removed.status_code, 200)
        self.assertFalse(removed.json()["has_logo"])
        self.assertEqual(self.ca.get(LOGO_FILE).status_code, 404)
        self.assertTrue(logo_file(path2).is_file())
        self.assertEqual(self.ca.get(document["pdf_url"]).status_code, 200)

        DocumentSettings.unscoped.filter(organization_id=organization).update(logo_path="../../etc/passwd")
        self.assertEqual(self.ca.get(LOGO_FILE).status_code, 404)

    # --- garde-fous de la base ---
    def test_12_database_guards(self):
        s1 = self.sell(self.ca, self.cycle_a)
        s2 = self.sell(self.ca, self.cycle_a)
        invoice = Document.unscoped.get(pk=self.issue(self.ca, "invoice", sale=s1["id"]).json()["id"])
        base = {"organization_id": invoice.organization_id, "year": invoice.year,
                "issued_on": date.today(), "content": {}}

        def refused(**fields):
            with self.assertRaises(IntegrityError):
                with transaction.atomic():
                    Document.unscoped.create(**{**base, **fields})

        refused(kind="invoice", sequence=invoice.sequence, number="ZZZ-1", sale_id=s2["id"])  # même numéro d'ordre
        refused(kind="invoice", sequence=77, number=invoice.number, sale_id=s2["id"])  # même numéro
        refused(kind="invoice", sequence=78, number="ZZZ-2", sale_id=s1["id"])  # deuxième facture pour la vente
        refused(kind="receipt", sequence=79, number="ZZZ-3", sale_id=s1["id"])  # reçu sans paiement

    # --- formulation des lignes ---
    def test_13_line_wording(self):
        def line(**fields):
            base = dict(product="eggs", price_tier="retail", egg_unit="egg", eggs_per_unit=1, quantity=3,
                        unit_price=100, total_amount=300, sale_type="count", weight_kg=None)
            return _lines(NS(**{**base, **fields}))[0]

        tray = line(egg_unit="tray", eggs_per_unit=30, price_tier="wholesale")
        self.assertEqual((tray["label"], tray["unit"]), ("Œufs, plateau de 30 (gros)", "plateau(x)"))
        crate = line(egg_unit="crate", eggs_per_unit=360)
        self.assertEqual((crate["label"], crate["unit"]), ("Œufs, carton de 360 (détail)", "carton(s)"))
        single = line()
        self.assertEqual((single["label"], single["unit"]), ("Œufs (détail)", "œuf(s)"))
        from decimal import Decimal
        weight = line(product="birds", sale_type="weight", weight_kg=Decimal("12.500"), quantity=6)
        self.assertEqual((weight["unit"], weight["quantity"]), ("kg", "12.5"))
        birds = line(product="birds")
        self.assertEqual((birds["label"], birds["unit"]), ("Poulets", "sujet(s)"))
