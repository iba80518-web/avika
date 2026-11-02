from django.core.cache import cache
from rest_framework.test import APIClient, APITestCase

from accounts.models import User

from .models import Farm, Membership, Organization
from .roles import Role

PASSWORD = "Mot-de-passe-solide-2026"


class ApiTests(APITestCase):
    def setUp(self):
        cache.clear()  # remet à zéro la limitation de débit entre les tests
        self.a = self.register("owner-a@test.com", "Exploitation A")
        self.b = self.register("owner-b@test.com", "Exploitation B")

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
            "/api/v1/auth/login/",
            {"identifier": identifier, "password": PASSWORD},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def auth(self, tokens, organization_id=None):
        client = APIClient()
        extra = {"HTTP_X_ORGANIZATION": str(organization_id)} if organization_id else {}
        client.credentials(HTTP_AUTHORIZATION="Bearer " + tokens["access"], **extra)
        return client

    def organization(self, tokens):
        return Organization.objects.get(pk=tokens["organization"]["id"])

    def names(self, response):
        return [farm["name"] for farm in response.json()["results"]]

    # --- inscription ---
    def test_01_register_creates_owner_and_tokens(self):
        response = APIClient().post(
            "/api/v1/auth/register/",
            {
                "full_name": "Mamadou",
                "email": "mamadou@test.com",
                "password": PASSWORD,
                "organization_name": "Ferme Mamadou",
                "reference_currency": "XOF",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertIn("access", body)
        self.assertIn("refresh", body)
        organization = Organization.objects.get(pk=body["organization"]["id"])
        self.assertEqual(organization.reference_currency, "XOF")
        membership = Membership.objects.get(user__email="mamadou@test.com")
        self.assertEqual(membership.role, Role.OWNER)

    def test_02_register_rejects_weak_password(self):
        response = APIClient().post(
            "/api/v1/auth/register/",
            {"full_name": "X", "email": "x@test.com", "password": "123", "organization_name": "F"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_03_register_rejects_duplicate_email_whatever_the_case(self):
        response = APIClient().post(
            "/api/v1/auth/register/",
            {
                "full_name": "Copie",
                "email": "OWNER-A@test.com",
                "password": PASSWORD,
                "organization_name": "Autre",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    # --- connexion ---
    def test_04_login_errors_do_not_reveal_whether_the_account_exists(self):
        client = APIClient()
        wrong = client.post(
            "/api/v1/auth/login/",
            {"identifier": "owner-a@test.com", "password": "mauvais"},
            format="json",
        )
        unknown = client.post(
            "/api/v1/auth/login/",
            {"identifier": "inconnu@test.com", "password": "mauvais"},
            format="json",
        )
        self.assertEqual(wrong.status_code, 401)
        self.assertEqual(unknown.status_code, 401)
        self.assertEqual(wrong.json(), unknown.json())

    def test_05_login_by_phone(self):
        response = APIClient().post(
            "/api/v1/auth/register/",
            {
                "full_name": "Sans email",
                "phone": "+224620000000",
                "password": PASSWORD,
                "organization_name": "Ferme Téléphone",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        tokens = self.login("+224620000000")
        self.assertIn("access", tokens)

    # --- isolation par l'API ---
    def test_06_farms_require_authentication(self):
        self.assertEqual(APIClient().get("/api/v1/farms/").status_code, 401)

    def test_07_each_owner_sees_only_own_farms(self):
        ca, cb = self.auth(self.a), self.auth(self.b)
        self.assertEqual(ca.post("/api/v1/farms/", {"name": "Site A1"}, format="json").status_code, 201)
        self.assertEqual(cb.post("/api/v1/farms/", {"name": "Site B1"}, format="json").status_code, 201)
        self.assertEqual(self.names(ca.get("/api/v1/farms/")), ["Site A1"])
        self.assertEqual(self.names(cb.get("/api/v1/farms/")), ["Site B1"])

    def test_08_other_owner_cannot_read_update_or_delete(self):
        ca, cb = self.auth(self.a), self.auth(self.b)
        farm_id = ca.post("/api/v1/farms/", {"name": "Site A1"}, format="json").json()["id"]
        url = f"/api/v1/farms/{farm_id}/"
        self.assertEqual(cb.get(url).status_code, 404)
        self.assertEqual(cb.patch(url, {"name": "Piratage"}, format="json").status_code, 404)
        self.assertEqual(cb.delete(url).status_code, 404)
        self.assertEqual(Farm.unscoped.get(pk=farm_id).name, "Site A1")

    def test_09_organization_sent_in_body_is_ignored(self):
        cb = self.auth(self.b)
        response = cb.post(
            "/api/v1/farms/",
            {"name": "Intrus", "organization": self.a["organization"]["id"]},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            Farm.unscoped.get(name="Intrus").organization_id, self.b["organization"]["id"]
        )

    # --- permissions ---
    def test_10_employee_can_list_but_not_create(self):
        employee = User.objects.create_user(
            email="emp@test.com", password=PASSWORD, full_name="Employé"
        )
        Membership.objects.create(
            user=employee, organization=self.organization(self.a), role=Role.EMPLOYEE
        )
        client = self.auth(self.login("emp@test.com"))
        self.assertEqual(client.get("/api/v1/farms/").status_code, 200)
        self.assertEqual(client.post("/api/v1/farms/", {"name": "X"}, format="json").status_code, 403)

    def test_11_observer_cannot_list_farms(self):
        observer = User.objects.create_user(
            email="obs@test.com", password=PASSWORD, full_name="Associé"
        )
        Membership.objects.create(
            user=observer, organization=self.organization(self.a), role=Role.OBSERVER
        )
        client = self.auth(self.login("obs@test.com"))
        self.assertEqual(client.get("/api/v1/farms/").status_code, 403)

    def test_12_several_organizations_require_a_valid_header(self):
        multi = self.register("multi@test.com", "Exploitation C")
        user = User.objects.get(email="multi@test.com")
        org_a = self.organization(self.a)
        Membership.objects.create(user=user, organization=org_a, role=Role.EMPLOYEE)
        self.auth(self.a).post("/api/v1/farms/", {"name": "Site A1"}, format="json")

        self.assertEqual(self.auth(multi).get("/api/v1/farms/").status_code, 403)
        in_a = self.auth(multi, org_a.pk).get("/api/v1/farms/")
        self.assertEqual(self.names(in_a), ["Site A1"])
        own = self.auth(multi, multi["organization"]["id"]).get("/api/v1/farms/")
        self.assertEqual(self.names(own), [])
        not_member = self.auth(multi, self.b["organization"]["id"]).get("/api/v1/farms/")
        self.assertEqual(not_member.status_code, 403)

    def test_13_suspended_membership_is_refused(self):
        Membership.objects.filter(user__email="owner-a@test.com").update(
            status=Membership.Status.SUSPENDED
        )
        self.assertEqual(self.auth(self.a).get("/api/v1/farms/").status_code, 403)

    def test_14_me_lists_effective_permissions(self):
        owner = self.auth(self.a).get("/api/v1/auth/me/").json()
        self.assertIn("view_profits", owner["memberships"][0]["permissions"])
        employee = User.objects.create_user(
            email="emp@test.com", password=PASSWORD, full_name="Employé"
        )
        Membership.objects.create(
            user=employee, organization=self.organization(self.a), role=Role.EMPLOYEE
        )
        data = self.auth(self.login("emp@test.com")).get("/api/v1/auth/me/").json()
        self.assertNotIn("view_profits", data["memberships"][0]["permissions"])
        self.assertIn("record_mortality", data["memberships"][0]["permissions"])

    # --- jetons ---
    def test_15_refresh_rotates_and_logout_revokes(self):
        client = APIClient()
        first = client.post("/api/v1/auth/refresh/", {"refresh": self.a["refresh"]}, format="json")
        self.assertEqual(first.status_code, 200)
        new_refresh = first.json()["refresh"]
        replay = client.post("/api/v1/auth/refresh/", {"refresh": self.a["refresh"]}, format="json")
        self.assertEqual(replay.status_code, 401)

        authed = self.auth({"access": first.json()["access"]})
        logout = authed.post("/api/v1/auth/logout/", {"refresh": new_refresh}, format="json")
        self.assertEqual(logout.status_code, 204)
        after = client.post("/api/v1/auth/refresh/", {"refresh": new_refresh}, format="json")
        self.assertEqual(after.status_code, 401)

    # --- règles métier ---
    def test_16_duplicate_farm_name_refused_within_but_not_across_organizations(self):
        ca, cb = self.auth(self.a), self.auth(self.b)
        self.assertEqual(ca.post("/api/v1/farms/", {"name": "Site"}, format="json").status_code, 201)
        self.assertEqual(ca.post("/api/v1/farms/", {"name": "Site"}, format="json").status_code, 400)
        self.assertEqual(cb.post("/api/v1/farms/", {"name": "Site"}, format="json").status_code, 201)
