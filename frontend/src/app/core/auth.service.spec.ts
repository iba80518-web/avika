import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { MeResponse } from './auth.models';
import { AuthService } from './auth.service';

const ME: MeResponse = {
  user: { id: 3, full_name: 'Dev Local', email: 'dev@avika.test', phone: null },
  memberships: [
    {
      organization: { id: 1, name: 'Ferme Dev', reference_currency: 'GNF' },
      role: 'owner',
      permissions: ['view_dashboard', 'view_finances'],
    },
    {
      organization: { id: 2, name: 'Autre ferme', reference_currency: 'XOF' },
      role: 'observer',
      permissions: ['view_dashboard'],
    },
  ],
};

describe('AuthService', () => {
  let auth: AuthService;
  let http: HttpTestingController;

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    auth = TestBed.inject(AuthService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  function loginAs(identifier = 'dev@avika.test') {
    auth.login(identifier, 'secret').subscribe();
    http.expectOne('/api/v1/auth/login/').flush({ access: 'A1', refresh: 'R1' });
    http.expectOne('/api/v1/auth/me/').flush(ME);
  }

  it('connecte, charge le profil et garde le jeton de rafraîchissement', () => {
    loginAs();
    expect(auth.isAuthenticated()).toBe(true);
    expect(auth.accessToken()).toBe('A1');
    expect(auth.user()?.full_name).toBe('Dev Local');
    expect(auth.activeOrganizationId()).toBe(1);
    expect(localStorage.getItem('avika.refresh')).toBe('R1');
  });

  it('refuse une connexion invalide et ne garde rien', () => {
    let failed = false;
    auth.login('dev@avika.test', 'mauvais').subscribe({ error: () => (failed = true) });
    http
      .expectOne('/api/v1/auth/login/')
      .flush({ detail: 'x' }, { status: 401, statusText: 'Unauthorized' });
    expect(failed).toBe(true);
    expect(auth.isAuthenticated()).toBe(false);
    expect(auth.accessToken()).toBeNull();
    expect(localStorage.getItem('avika.refresh')).toBeNull();
  });

  it('can() lit les droits de l’exploitation active', () => {
    loginAs();
    expect(auth.can('view_finances')).toBe(true);
    expect(auth.can('manage_users')).toBe(false);
  });

  it('restoreSession sans jeton répond faux sans appeler le serveur', () => {
    let result: boolean | null = null;
    auth.restoreSession().subscribe((value) => (result = value));
    expect(result).toBe(false);
  });

  it('restoreSession avec un jeton rouvre la session', () => {
    localStorage.setItem('avika.refresh', 'R1');
    let result: boolean | null = null;
    auth.restoreSession().subscribe((value) => (result = value));
    http.expectOne('/api/v1/auth/refresh/').flush({ access: 'A2', refresh: 'R2' });
    http.expectOne('/api/v1/auth/me/').flush(ME);
    expect(result).toBe(true);
    expect(localStorage.getItem('avika.refresh')).toBe('R2');
  });

  it('restoreSession avec un jeton refusé ferme la session', () => {
    localStorage.setItem('avika.refresh', 'perime');
    let result: boolean | null = null;
    auth.restoreSession().subscribe((value) => (result = value));
    http
      .expectOne('/api/v1/auth/refresh/')
      .flush({ detail: 'x' }, { status: 401, statusText: 'Unauthorized' });
    expect(result).toBe(false);
    expect(localStorage.getItem('avika.refresh')).toBeNull();
  });

  it('logout efface la session même si le serveur échoue', () => {
    loginAs();
    auth.logout().subscribe();
    http
      .expectOne('/api/v1/auth/logout/')
      .flush({ detail: 'x' }, { status: 500, statusText: 'Server Error' });
    expect(auth.isAuthenticated()).toBe(false);
    expect(auth.accessToken()).toBeNull();
    expect(localStorage.getItem('avika.refresh')).toBeNull();
  });
});
