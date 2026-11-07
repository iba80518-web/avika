from unittest import mock

from django.db import OperationalError
from rest_framework.test import APIClient, APITestCase


class StatusTests(APITestCase):
    def test_01_status_is_public_and_says_ok(self):
        response = APIClient().get("/api/v1/status/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "database": "ok"})

    def test_02_status_says_503_when_the_database_is_down(self):
        with mock.patch("core.status.connection.cursor", side_effect=OperationalError("down")):
            response = APIClient().get("/api/v1/status/")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["status"], "error")
