# Code ISO 4217 : (nom, nombre de décimales de l'unité minimale)
CURRENCIES = {
    "GNF": ("Franc guinéen", 0),
    "XOF": ("Franc CFA (Afrique de l'Ouest)", 0),
    "XAF": ("Franc CFA (Afrique centrale)", 0),
    "USD": ("Dollar américain", 2),
    "EUR": ("Euro", 2),
    "GMD": ("Dalasi gambien", 2),
}

CURRENCY_CHOICES = [(code, f"{code} - {name}") for code, (name, _) in CURRENCIES.items()]
