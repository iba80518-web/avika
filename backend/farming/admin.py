from django.contrib import admin

from tenants.admin import TenantAdmin

from .models import Coop, Cycle, FlockEvent


class ReadOnlyTenantAdmin(TenantAdmin):
    """Le journal du cheptel se consulte, il ne se modifie pas."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(Coop, TenantAdmin)
admin.site.register(Cycle, TenantAdmin)
admin.site.register(FlockEvent, ReadOnlyTenantAdmin)
