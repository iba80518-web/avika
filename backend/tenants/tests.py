from django.db import IntegrityError, transaction
from django.test import TestCase

from accounts.models import User

from .models import Membership, MembershipPermission, Organization
from .permissions import has_permission
from .roles import PERMISSION_CODES, Role


class PermissionTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Ferme A")

    def make(self, email, role, **kwargs):
        user = User.objects.create_user(email=email, password="mot-de-passe-test-123", full_name=email)
        return Membership.objects.create(user=user, organization=self.org, role=role, **kwargs)

    def test_owner_has_everything(self):
        owner = self.make("owner@test.com", Role.OWNER)
        for code in PERMISSION_CODES:
            self.assertTrue(has_permission(owner, code), code)

    def test_employee_can_record_mortality(self):
        employee = self.make("emp@test.com", Role.EMPLOYEE)
        self.assertTrue(has_permission(employee, "record_mortality"))

    def test_employee_cannot_view_profits(self):
        employee = self.make("emp@test.com", Role.EMPLOYEE)
        self.assertFalse(has_permission(employee, "view_profits"))
        self.assertFalse(has_permission(employee, "view_finances"))

    def test_override_grants_permission(self):
        manager = self.make("mgr@test.com", Role.MANAGER)
        self.assertFalse(has_permission(manager, "view_finances"))
        MembershipPermission.objects.create(membership=manager, permission="view_finances", granted=True)
        self.assertTrue(has_permission(manager, "view_finances"))

    def test_override_can_remove_permission(self):
        employee = self.make("emp@test.com", Role.EMPLOYEE)
        MembershipPermission.objects.create(membership=employee, permission="record_mortality", granted=False)
        self.assertFalse(has_permission(employee, "record_mortality"))

    def test_suspended_member_has_nothing(self):
        member = self.make("mgr@test.com", Role.MANAGER, status=Membership.Status.SUSPENDED)
        self.assertFalse(has_permission(member, "view_dashboard"))

    def test_user_needs_email_or_phone(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                User.objects.create(full_name="Sans contact")

    def test_one_membership_per_user_and_organization(self):
        member = self.make("mgr@test.com", Role.MANAGER)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Membership.objects.create(user=member.user, organization=self.org, role=Role.OWNER)
