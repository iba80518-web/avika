import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { Observable, catchError, finalize, map, of, shareReplay, switchMap, tap, throwError } from 'rxjs';

import { API_BASE } from './api.config';
import { MeResponse, Membership, Tokens } from './auth.models';

const REFRESH_KEY = 'avika.refresh';
const ORGANIZATION_KEY = 'avika.organization';
const PROFILE_KEY = 'avika.profile';

// Le stockage du navigateur peut être absent ou refusé (navigation privée) : on ne plante jamais.
function readStorage(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeStorage(key: string, value: string | null): void {
  try {
    if (value === null) {
      localStorage.removeItem(key);
    } else {
      localStorage.setItem(key, value);
    }
  } catch {
    // Pas de stockage disponible : la session durera jusqu'à la fermeture de l'onglet.
  }
}

// Coupure du réseau (et non refus du serveur) : la session reste valable.
function isNetworkError(error: unknown): boolean {
  return error instanceof HttpErrorResponse && error.status === 0;
}

// Vide les données de lecture gardées par le service worker : à faire à chaque fin de session,
// pour qu'un téléphone prêté ne montre rien de l'utilisateur précédent.
function clearDataCache(): void {
  if (typeof caches === 'undefined') return;
  void caches
    .keys()
    .then((keys) =>
      Promise.all(keys.filter((key) => key.includes(':data:')).map((key) => caches.delete(key))),
    )
    .catch(() => undefined);
}

/**
 * Connexion, session et droits de l'utilisateur.
 *
 * - Le jeton d'accès (15 minutes) vit seulement en mémoire.
 * - Le jeton de rafraîchissement (14 jours) est gardé dans le navigateur pour rouvrir la session.
 */
@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);

  private readonly accessSignal = signal<string | null>(null);
  private readonly meSignal = signal<MeResponse | null>(null);
  private readonly organizationSignal = signal<number | null>(null);
  private refreshInFlight: Observable<string> | null = null;

  /** Vrai quand la session a été rouverte sans réseau, avec le profil gardé sur le téléphone. */
  readonly offlineSession = signal(false);

  readonly accessToken = this.accessSignal.asReadonly();
  readonly isAuthenticated = computed(() => this.meSignal() !== null);
  readonly user = computed(() => this.meSignal()?.user ?? null);
  readonly memberships = computed(() => this.meSignal()?.memberships ?? []);

  /** Exploitation active : celle choisie, sinon la première de l'utilisateur. */
  readonly activeMembership = computed<Membership | null>(() => {
    const memberships = this.memberships();
    return (
      memberships.find((item) => item.organization.id === this.organizationSignal()) ?? memberships[0] ?? null
    );
  });
  readonly activeOrganizationId = computed(() => this.activeMembership()?.organization.id ?? null);

  constructor() {
    // Le réseau revient : on revalide la session ouverte hors connexion.
    if (typeof window !== 'undefined') {
      window.addEventListener('online', () => {
        if (this.offlineSession()) this.revalidate().subscribe({ error: () => undefined });
      });
    }
  }

  private revalidate(): Observable<void> {
    return this.refreshAccess().pipe(
      switchMap(() => this.loadProfile()),
      catchError((error: unknown) => {
        if (isNetworkError(error)) return of(undefined);
        this.clearSession();
        return throwError(() => error);
      }),
    );
  }

  // Rouvre la session avec le profil gardé sur le téléphone (aucun appel au serveur).
  private restoreOffline(): boolean {
    const raw = readStorage(PROFILE_KEY);
    if (raw === null) return false;
    try {
      const me = JSON.parse(raw) as MeResponse;
      this.meSignal.set(me);
      const saved = Number(readStorage(ORGANIZATION_KEY));
      const known = me.memberships.some((item) => item.organization.id === saved);
      this.organizationSignal.set(known ? saved : (me.memberships[0]?.organization.id ?? null));
      this.offlineSession.set(true);
      return true;
    } catch {
      return false;
    }
  }

  /** Vrai si l'utilisateur a le droit demandé dans l'exploitation active. */
  can(permission: string): boolean {
    return this.activeMembership()?.permissions.includes(permission) ?? false;
  }

  hasRefreshToken(): boolean {
    return readStorage(REFRESH_KEY) !== null;
  }

  login(identifier: string, password: string): Observable<void> {
    return this.http.post<Tokens>(`${API_BASE}/auth/login/`, { identifier, password }).pipe(
      tap((tokens) => {
        this.accessSignal.set(tokens.access);
        writeStorage(REFRESH_KEY, tokens.refresh);
      }),
      switchMap(() => this.loadProfile()),
      catchError((error: unknown) => {
        this.clearSession();
        return throwError(() => error);
      }),
    );
  }

  /** Rouvre la session après un rechargement de la page, à partir du jeton de rafraîchissement. */
  restoreSession(): Observable<boolean> {
    if (this.isAuthenticated()) {
      return of(true);
    }
    if (!this.hasRefreshToken()) {
      return of(false);
    }
    return this.refreshAccess().pipe(
      switchMap(() => this.loadProfile()),
      map(() => true),
      catchError((error: unknown) => {
        // Réseau absent : on garde la session (et le jeton) ; seul un refus du serveur déconnecte.
        if (isNetworkError(error)) return of(this.restoreOffline());
        this.clearSession();
        return of(false);
      }),
    );
  }

  /** Obtient un nouveau jeton d'accès. Plusieurs demandes simultanées partagent un seul appel. */
  refreshAccess(): Observable<string> {
    const refresh = readStorage(REFRESH_KEY);
    if (refresh === null) {
      return throwError(() => new Error('Aucun jeton de rafraîchissement.'));
    }
    if (this.refreshInFlight === null) {
      this.refreshInFlight = this.http
        .post<{ access: string; refresh?: string }>(`${API_BASE}/auth/refresh/`, { refresh })
        .pipe(
          tap((tokens) => {
            this.accessSignal.set(tokens.access);
            if (tokens.refresh) {
              writeStorage(REFRESH_KEY, tokens.refresh);
            }
          }),
          map((tokens) => tokens.access),
          finalize(() => {
            this.refreshInFlight = null;
          }),
          shareReplay({ bufferSize: 1, refCount: false }),
        );
    }
    return this.refreshInFlight;
  }

  /** Déconnexion : révoque le jeton côté serveur si possible, et efface la session dans tous les cas. */
  logout(): Observable<void> {
    const refresh = readStorage(REFRESH_KEY);
    const revoke$: Observable<unknown> =
      refresh === null ? of(null) : this.http.post(`${API_BASE}/auth/logout/`, { refresh });
    return revoke$.pipe(
      catchError(() => of(null)),
      tap(() => this.clearSession()),
      map(() => undefined),
    );
  }

  /** Efface tout ce que la session garde, en mémoire et dans le navigateur. */
  clearSession(): void {
    this.accessSignal.set(null);
    this.meSignal.set(null);
    this.organizationSignal.set(null);
    writeStorage(REFRESH_KEY, null);
    writeStorage(ORGANIZATION_KEY, null);
    writeStorage(PROFILE_KEY, null);
    this.offlineSession.set(false);
    clearDataCache();
  }

  private loadProfile(): Observable<void> {
    return this.http.get<MeResponse>(`${API_BASE}/auth/me/`).pipe(
      tap((me) => {
        this.meSignal.set(me);
        writeStorage(PROFILE_KEY, JSON.stringify(me));
        this.offlineSession.set(false);
        const saved = Number(readStorage(ORGANIZATION_KEY));
        const known = me.memberships.some((item) => item.organization.id === saved);
        const chosen = known ? saved : (me.memberships[0]?.organization.id ?? null);
        this.organizationSignal.set(chosen);
        writeStorage(ORGANIZATION_KEY, chosen === null ? null : String(chosen));
      }),
      map(() => undefined),
    );
  }
}
