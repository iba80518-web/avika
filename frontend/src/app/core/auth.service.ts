import { HttpClient } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { Observable, catchError, finalize, map, of, shareReplay, switchMap, tap, throwError } from 'rxjs';

import { API_BASE } from './api.config';
import { MeResponse, Membership, Tokens } from './auth.models';

const REFRESH_KEY = 'avika.refresh';
const ORGANIZATION_KEY = 'avika.organization';

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
      catchError(() => {
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
  }

  private loadProfile(): Observable<void> {
    return this.http.get<MeResponse>(`${API_BASE}/auth/me/`).pipe(
      tap((me) => {
        this.meSignal.set(me);
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
