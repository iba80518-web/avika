from django.contrib import admin

from .models import Membership, MembershipPermission, Organization

admin.site.register(Organization)
admin.site.register(Membership)
admin.site.register(MembershipPermission)
