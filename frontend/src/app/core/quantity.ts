const quantities = new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 3 });

// Le serveur renvoie les quantités en texte ("70.000") : on les affiche sans zéros inutiles.
export function formatQuantity(value: string | number): string {
  return quantities.format(Number(value));
}

// Niveau de la jauge : à moitié au seuil d'alerte, pleine à deux fois le seuil.
export function levelPercent(stock: string, threshold: string): number {
  const current = Number(stock);
  const limit = Number(threshold);
  if (limit <= 0) return current > 0 ? 100 : 0;
  return Math.max(0, Math.min(100, Math.round((current / (limit * 2)) * 100)));
}
