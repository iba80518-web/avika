from django.contrib import admin

from tenants.admin import TenantAdmin

from .models import Customer, Expense, Payment, Sale


class ReadOnlyTenantAdmin(TenantAdmin):
    """Les paiements se consultent, ils ne se modifient pas."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(Customer, TenantAdmin)
admin.site.register(Expense, TenantAdmin)
admin.site.register(Sale, TenantAdmin)
admin.site.register(Payment, ReadOnlyTenantAdmin)
