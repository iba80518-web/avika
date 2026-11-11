const integer = new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 0 });

export function formatNumber(value: number): string {
  return integer.format(value);
}

// Montants entiers (unité minimale), ex. 8 100 000 GNF.
export function formatMoney(amount: number, currency = 'GNF'): string {
  return `${integer.format(amount)} ${currency}`;
}

// Version courte pour les grandes cartes : 8,1 M, 950 k, 1,2 Md.
export function formatCompact(value: number): string {
  const abs = Math.abs(value);
  const short = (n: number, suffix: string) =>
    `${(Math.round(n * 10) / 10).toString().replace('.', ',')} ${suffix}`;
  if (abs >= 1_000_000_000) return short(value / 1_000_000_000, 'Md');
  if (abs >= 1_000_000) return short(value / 1_000_000, 'M');
  if (abs >= 10_000) return short(value / 1_000, 'k');
  return integer.format(value);
}
