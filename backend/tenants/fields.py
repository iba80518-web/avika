from rest_framework import serializers


class TenantPrimaryKeyRelatedField(serializers.PrimaryKeyRelatedField):
    """Relation limitée aux objets de l'exploitation active (sinon : 400)."""

    def __init__(self, model, **kwargs):
        self.tenant_model = model
        kwargs["queryset"] = model.unscoped.none()  # simple valeur de départ
        super().__init__(**kwargs)

    def get_queryset(self):
        return self.tenant_model.objects.all()
