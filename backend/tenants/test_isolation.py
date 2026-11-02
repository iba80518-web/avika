from django.db import IntegrityError, transaction
from django.test import TestCase

from .context import (
    CrossTenantError,
    TenantContextMissing,
    get_current_organization_id,
    organization_context,
)
from .models import Farm, Organization


class TenantIsolationTests(TestCase):
    def setUp(self):
        self.org_a = Organization.objects.create(name="Exploitation A")
        self.org_b = Organization.objects.create(name="Exploitation B")
        with organization_context(self.org_a):
            self.farm_a1 = Farm.objects.create(name="Site A1")
            Farm.objects.create(name="Site A2")
        with organization_context(self.org_b):
            self.farm_b1 = Farm.objects.create(name="Site B1")

    def test_1_each_organization_sees_only_its_own_data(self):
        with organization_context(self.org_a):
            self.assertEqual(
                set(Farm.objects.values_list("name", flat=True)), {"Site A1", "Site A2"}
            )
        with organization_context(self.org_b):
            self.assertEqual(list(Farm.objects.values_list("name", flat=True)), ["Site B1"])

    def test_2_b_cannot_fetch_an_object_of_a_by_id(self):
        with organization_context(self.org_b):
            with self.assertRaises(Farm.DoesNotExist):
                Farm.objects.get(pk=self.farm_a1.pk)

    def test_3_query_without_active_organization_is_refused(self):
        with self.assertRaises(TenantContextMissing):
            list(Farm.objects.all())

    def test_4_create_without_organization_is_refused(self):
        with self.assertRaises(TenantContextMissing):
            Farm.objects.create(name="Orpheline")

    def test_5_create_takes_the_active_organization(self):
        with organization_context(self.org_a):
            farm = Farm.objects.create(name="Nouveau site")
        self.assertEqual(farm.organization_id, self.org_a.pk)

    def test_6_cannot_write_an_object_into_another_organization(self):
        with organization_context(self.org_b):
            self.farm_a1.name = "Piratage"
            with self.assertRaises(CrossTenantError):
                self.farm_a1.save()
            with self.assertRaises(CrossTenantError):
                Farm.objects.create(name="Intrus", organization=self.org_a)
        self.assertEqual(Farm.unscoped.get(pk=self.farm_a1.pk).name, "Site A1")

    def test_7_bulk_update_and_delete_cannot_touch_the_other_organization(self):
        with organization_context(self.org_b):
            updated = Farm.objects.filter(pk=self.farm_a1.pk).update(name="Piratage")
            deleted, _ = Farm.objects.filter(pk=self.farm_a1.pk).delete()
        self.assertEqual(updated, 0)
        self.assertEqual(deleted, 0)
        self.assertEqual(Farm.unscoped.get(pk=self.farm_a1.pk).name, "Site A1")

    def test_8_context_is_reset_after_the_block(self):
        with organization_context(self.org_a):
            self.assertEqual(get_current_organization_id(), self.org_a.pk)
        self.assertIsNone(get_current_organization_id())

    def test_9_same_name_allowed_across_organizations_but_not_within_one(self):
        with organization_context(self.org_b):
            Farm.objects.create(name="Site A1")  # même nom que chez A : autorisé
        with organization_context(self.org_a):
            with self.assertRaises(IntegrityError):
                with transaction.atomic():
                    Farm.objects.create(name="Site A1")
