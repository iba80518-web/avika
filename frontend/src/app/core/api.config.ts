/**
 * Adresse de base de l'API.
 *
 * Elle est relative (sans domaine) : en développement, le proxy d'Angular (proxy.conf.json)
 * transmet « /api » à Django ; en production, Nginx fera la même chose sous un seul domaine.
 * Aucun réglage par environnement n'est donc nécessaire.
 */
export const API_BASE = '/api/v1';
