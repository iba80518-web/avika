// Saisie tolérante : "12,5", "1 250" ou "12.5" donnent le bon nombre. Vide donne 0.
export function parseNumber(raw: string): number {
  return Number(raw.replace(/\s/g, '').replace(',', '.'));
}
