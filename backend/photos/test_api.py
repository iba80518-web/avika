import io
import shutil
import tempfile
from pathlib import Path
from uuid import uuid4

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image
from rest_framework.test import APIClient, APITestCase

from accounts.models import User
from tenants.models import Membership
from tenants.roles import Role

PASSWORD = "Mot-de-passe-solide-2026"
URL = "/api/v1/photos/"
DAY = "2026-10-03"
TMP = Path(tempfile.mkdtemp(prefix="avika-photos-test-"))


def make_image(size=(2400, 1800), with_metadata=False):
    image = Image.new("RGB", size, (200, 120, 40))
    buffer = io.BytesIO()
    if with_metadata:
        exif = Image.Exif()
        exif[0x010F] = "TelephoneTest"  # fabricant
        exif[0x013B] = "Eleveur Secret"  # auteur
        image.save(buffer, "JPEG", exif=exif)
    else:
        image.save(buffer, "JPEG")
    return buffer.getvalue()


@override_settings(PHOTOS_ROOT=TMP)
class PhotoApiTests(APITestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TMP, ignore_errors=True)
        super().tearDownClass()

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

    def send(self, client=None, data=None, name="p.jpg", content_type="image/jpeg", **extra):
        body = {
            "cycle": self.cycle["id"], "kind": "eggs", "taken_date": DAY, "uuid": str(uuid4()),
            "image": SimpleUploadedFile(
                name, data if data is not None else make_image(), content_type=content_type
            ),
        }
        body.update(extra)
        return (client or self.ca).post(URL, body, format="multipart")

    def read_file(self, client, photo):
        response = client.get(photo["file_url"])
        self.assertEqual(response.status_code, 200)
        return b"".join(response.streaming_content), response

    # --- tests ---
    def test_01_envoi_puis_lecture_image_reduite_a_1600_pixels(self):
        response = self.send(kind="eggs")
        self.assertEqual(response.status_code, 201, response.content)
        photo = response.json()
        self.assertEqual(photo["kind"], "eggs")
        self.assertEqual(max(photo["width"], photo["height"]), 1600)
        content, served = self.read_file(self.ca, photo)
        self.assertEqual(served["Content-Type"], "image/jpeg")
        self.assertEqual(served["Cache-Control"], "private, no-store")
        self.assertEqual(Image.open(io.BytesIO(content)).format, "JPEG")

    def test_02_les_metadonnees_sont_effacees(self):
        original = make_image(with_metadata=True)
        self.assertEqual(Image.open(io.BytesIO(original)).getexif().get(0x010F), "TelephoneTest")
        photo = self.send(data=original, kind="mortality").json()
        content, _ = self.read_file(self.ca, photo)
        self.assertEqual(len(Image.open(io.BytesIO(content)).getexif()), 0)
        self.assertNotIn(b"TelephoneTest", content)
        self.assertNotIn(b"Eleveur Secret", content)

    def test_03_renvoyer_la_meme_photo_ne_cree_pas_de_doublon(self):
        identifier = str(uuid4())
        first = self.send(uuid=identifier)
        again = self.send(uuid=identifier)
        self.assertEqual(first.status_code, 201, first.content)
        self.assertEqual(again.status_code, 200, again.content)
        self.assertEqual(first.json()["id"], again.json()["id"])
        self.assertEqual(self.ca.get(URL).json()["count"], 1)

    def test_04_droits_envoyer_sans_voir_et_voir_sans_envoyer(self):
        employee = self.member(self.a, "emp@test.com", Role.EMPLOYEE)
        sent = self.send(client=employee).json()
        self.assertEqual(employee.get(URL).status_code, 403)
        self.assertEqual(employee.get(sent["file_url"]).status_code, 403)

        manager = self.member(self.a, "man@test.com", Role.MANAGER)
        self.assertEqual(self.send(client=manager).status_code, 201)
        self.assertEqual(manager.get(URL).status_code, 403)

        vet = self.member(self.a, "vet@test.com", Role.VET)
        self.assertEqual(vet.get(URL).status_code, 200)
        self.assertEqual(vet.get(sent["file_url"]).status_code, 200)
        self.assertEqual(self.send(client=vet).status_code, 403)

        accountant = self.member(self.a, "compta@test.com", Role.ACCOUNTANT)
        self.assertEqual(accountant.get(URL).status_code, 403)
        self.assertEqual(self.send(client=accountant).status_code, 403)
        self.assertIn(APIClient().get(URL).status_code, (401, 403))

    def test_05_une_exploitation_ne_voit_pas_les_photos_dune_autre(self):
        photo = self.send().json()
        self.assertEqual(self.cb.get(URL).json()["count"], 0)
        self.assertEqual(self.cb.get(photo["file_url"]).status_code, 404)
        self.assertEqual(self.send(client=self.cb).status_code, 400)

    def test_06_un_fichier_qui_nest_pas_une_image_est_refuse(self):
        response = self.send(data=b"ceci n'est pas une image", name="p.jpg")
        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(self.ca.get(URL).json()["count"], 0)

    def test_07_une_image_trop_lourde_est_refusee(self):
        with self.settings(PHOTO_MAX_UPLOAD_BYTES=1000):
            response = self.send()
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("trop lourde", response.content.decode())

    def test_08_liens_avec_les_ramassages_et_types_de_bande(self):
        collection = self.create(
            self.ca, "/api/v1/egg-collections/",
            {"cycle": self.cycle["id"], "collected_date": DAY, "collected": 300, "broken": 10,
             "uuid": str(uuid4())},
        )
        linked = self.send(egg_collection=collection["id"])
        self.assertEqual(linked.status_code, 201, linked.content)
        self.assertEqual(linked.json()["egg_collection"], collection["id"])
        # Une photo de volailles mortes ne se lie pas à un ramassage d'œufs.
        wrong = self.send(kind="mortality", egg_collection=collection["id"])
        self.assertEqual(wrong.status_code, 400, wrong.content)
        # Des œufs ne se photographient pas dans une bande de poulets de chair.
        broiler = self.send(cycle=self.broiler_cycle["id"], kind="eggs")
        self.assertEqual(broiler.status_code, 400, broiler.content)
        # Mais une mortalité de poulets de chair se photographie.
        dead = self.send(cycle=self.broiler_cycle["id"], kind="mortality")
        self.assertEqual(dead.status_code, 201, dead.content)

    def test_09_date_future_et_suppression_refusees(self):
        self.assertEqual(self.send(taken_date="2099-01-01").status_code, 400)
        photo = self.send().json()
        self.assertIn(self.ca.delete(f"{URL}{photo['id']}/").status_code, (403, 405))
        self.assertEqual(self.ca.get(f"{URL}{photo['id']}/").status_code, 200)

    def test_10_la_photo_se_lie_au_ramassage_par_son_identifiant(self):
        collection_uuid = str(uuid4())
        collection = self.create(
            self.ca, "/api/v1/egg-collections/",
            {"cycle": self.cycle["id"], "collected_date": DAY, "collected": 300, "broken": 10,
             "uuid": collection_uuid},
        )
        linked = self.send(egg_collection_uuid=collection_uuid)
        self.assertEqual(linked.status_code, 201, linked.content)
        self.assertEqual(linked.json()["egg_collection"], collection["id"])
        unknown = self.send(egg_collection_uuid=str(uuid4()))
        self.assertEqual(unknown.status_code, 400, unknown.content)
        self.assertIn("Ramassage introuvable", unknown.content.decode())
