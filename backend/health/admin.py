from django.contrib import admin

from tenants.admin import TenantAdmin

from .models import HealthTask, HealthTemplate, HealthTemplateItem

admin.site.register(HealthTemplate, TenantAdmin)
admin.site.register(HealthTemplateItem, TenantAdmin)
admin.site.register(HealthTask, TenantAdmin)
