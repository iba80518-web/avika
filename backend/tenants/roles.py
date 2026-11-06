from django.db import models


class Role(models.TextChoices):
    OWNER = "owner", "Propriétaire"
    MANAGER = "manager", "Gestionnaire"
    EMPLOYEE = "employee", "Employé"
    ACCOUNTANT = "accountant", "Comptable"
    VET = "vet", "Vétérinaire"
    OBSERVER = "observer", "Observateur / Associé"


PERMISSIONS = [
    ("view_dashboard", "Voir le tableau de bord"),
    ("view_farming", "Voir poulaillers, cycles et mortalités"),
    ("manage_coops", "Gérer les poulaillers"),
    ("manage_cycles", "Gérer les cycles"),
    ("record_mortality", "Enregistrer les mortalités"),
    ("manage_feed", "Gérer aliments et stocks"),
    ("manage_health", "Gérer vaccins et traitements"),
    ("manage_expenses", "Gérer les dépenses"),
    ("manage_sales", "Gérer les ventes"),
    ("manage_customers", "Gérer les clients"),
    ("manage_suppliers", "Gérer les fournisseurs"),
    ("view_finances", "Voir les finances"),
    ("view_profits", "Voir les bénéfices"),
    ("generate_reports", "Générer les rapports"),
    ("manage_users", "Gérer les utilisateurs"),
    ("manage_subscription", "Gérer l'abonnement"),
    ("view_audit", "Consulter le journal d'audit"),
]

PERMISSION_CODES = [code for code, _ in PERMISSIONS]
PERMISSION_CHOICES = PERMISSIONS

# Permissions accordées par défaut à chaque rôle.
# Les cases « à accorder par le propriétaire » du cahier des charges
# (ex. voir_finances pour un gestionnaire) passent par des exceptions.
DEFAULT_ROLE_PERMISSIONS = {
    Role.OWNER: set(PERMISSION_CODES),
    Role.MANAGER: {
        "view_dashboard", "view_farming", "manage_coops", "manage_cycles",
        "record_mortality", "manage_feed", "manage_health", "manage_expenses",
        "manage_sales", "manage_customers", "manage_suppliers", "generate_reports",
    },
    Role.EMPLOYEE: {
        "view_dashboard", "view_farming", "record_mortality", "manage_feed", "manage_health",
    },
    Role.ACCOUNTANT: {
        "view_dashboard", "manage_expenses", "manage_sales", "manage_customers",
        "manage_suppliers", "view_finances", "generate_reports",
    },
    Role.VET: {"view_farming", "manage_health"},
    Role.OBSERVER: {"view_dashboard"},
}
