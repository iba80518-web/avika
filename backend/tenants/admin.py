from django.contrib import admin

from .models import Farm, Membership, MembershipPermission, Organization


class TenantAdmin(admin.ModelAdmin):
    """Administration d'une table métier : voit toutes les exploitations (usage staff)."""

    def get_queryset(self, request):
        queryset = self.model.unscoped.all()
        ordering = self.get_ordering(request)
        return queryset.order_by(*ordering) if ordering else queryset


admin.site.register(Organization)
admin.site.register(Membership)
admin.site.register(MembershipPermission)
admin.site.register(Farm, TenantAdmin)
