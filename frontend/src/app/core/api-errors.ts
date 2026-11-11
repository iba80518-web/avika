import { HttpErrorResponse } from '@angular/common/http';

// Erreurs de validation du serveur, champ par champ : { name: "Ce poulailler a déjà un cycle..." }.
export function fieldErrors(error: unknown): Record<string, string> {
  const result: Record<string, string> = {};
  if (
    error instanceof HttpErrorResponse &&
    error.status === 400 &&
    error.error &&
    typeof error.error === 'object' &&
    !Array.isArray(error.error)
  ) {
    for (const [key, value] of Object.entries(error.error as Record<string, unknown>)) {
      const text = Array.isArray(value) ? value[0] : value;
      if (typeof text === 'string') result[key] = text;
    }
  }
  return result;
}

// Un message lisible pour l'éleveur, quelle que soit la cause de l'échec.
export function firstMessage(
  error: unknown,
  fallback = 'L’opération a échoué. Réessayez dans un instant.',
): string {
  if (error instanceof HttpErrorResponse) {
    if (error.status === 0) return 'Pas de connexion. Réessayez quand le réseau revient.';
    if (error.status === 403) return 'Vous n’avez pas le droit d’effectuer cette action.';
    const body: unknown = error.error;
    if (body && typeof body === 'object') {
      const first = Object.values(body as Record<string, unknown>)[0];
      const text = Array.isArray(first) ? first[0] : first;
      if (typeof text === 'string') return text;
    }
  }
  return fallback;
}
