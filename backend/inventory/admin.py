from django.contrib import admin

from tenants.admin import TenantAdmin

from .models import Product, ProductUnit, StockMovement, Supplier


class ReadOnlyTenantAdmin(TenantAdmin):
    """Le journal de stock se consulte, il ne se modifie pas."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(Supplier, TenantAdmin)
admin.site.register(Product, TenantAdmin)
admin.site.register(ProductUnit, TenantAdmin)
admin.site.register(StockMovement, ReadOnlyTenantAdmin)
