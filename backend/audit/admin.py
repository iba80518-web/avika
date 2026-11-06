from django.contrib import admin

from tenants.admin import TenantAdmin

from .models import AuditLog


class ReadOnlyTenantAdmin(TenantAdmin):
    """Le journal d'audit se consulte, il ne se modifie jamais."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(AuditLog, ReadOnlyTenantAdmin)
