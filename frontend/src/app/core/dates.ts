// Date du jour à l'heure locale de l'appareil, au format AAAA-MM-JJ (celui de l'API).
export function localToday(): string {
  return new Date().toLocaleDateString('en-CA');
}

// Numéro du jour d'une bande : le jour de la mise en place est le jour 1.
export function dayNumber(start: string, today: string = localToday()): number {
  const [y1, m1, d1] = start.split('-').map(Number);
  const [y2, m2, d2] = today.split('-').map(Number);
  const days = (Date.UTC(y2, m2 - 1, d2) - Date.UTC(y1, m1 - 1, d1)) / 86_400_000;
  return Math.round(days) + 1;
}

export function shortDate(iso: string): string {
  return new Date(`${iso}T00:00:00`).toLocaleDateString('fr-FR', {
    day: 'numeric',
    month: 'short',
  });
}
