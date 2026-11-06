from django.conf import settings
from django.db import models

from farming.models import ImmutableRecordError
from tenants.models import TenantModel


class AuditLog(TenantModel):
    """Trace d'une action sensible : qui, quand, quoi, avant, après. Jamais modifiable."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    # Code de l'action : « sale.created », « payment.created », « expense.updated »...
    action = models.CharField(max_length=60)
    object_type = models.CharField(max_length=60, blank=True)
    object_id = models.BigIntegerField(null=True, blank=True)
    summary = models.CharField(max_length=255, blank=True)
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["organization", "created_at"]),
            models.Index(fields=["organization", "object_type", "object_id"]),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ImmutableRecordError("Le journal d'audit ne peut pas être modifié.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ImmutableRecordError("Le journal d'audit ne peut pas être supprimé.")

    def __str__(self):
        return f"{self.action} #{self.object_id} ({self.created_at:%Y-%m-%d})"
