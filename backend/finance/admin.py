from django.contrib import admin

from tenants.admin import TenantAdmin

from .models import Customer, Expense

admin.site.register(Customer, TenantAdmin)
admin.site.register(Expense, TenantAdmin)
