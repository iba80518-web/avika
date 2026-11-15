import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { AuthService } from './auth.service';

const ME = {
  user: { id: 1, full_name: 'Awa Diallo', email: 'awa@test.com' },
  memberships: [
    { organization: { id: 7, name: 'Ferme Test' }, role: 'owner', permissions: ['manage_eggs'] },
  ],
};

describe('AuthService — session hors connexion', () => {
  let auth: AuthService;
  let http: HttpTestingController;

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    auth = TestBed.inject(AuthService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    http.verify();
    localStorage.clear();
  });

  it('rouvre la session sans réseau grâce au profil gardé sur le téléphone', () => {
    localStorage.setItem('avika.refresh', 'r1');
    localStorage.setItem('avika.profile', JSON.stringify(ME));
    localStorage.setItem('avika.organization', '7');
    let result: boolean | undefined;
    auth.restoreSession().subscribe((value) => (result = value));
    http.expectOne('/api/v1/auth/refresh/').error(new ProgressEvent('error'));
    expect(result).toBe(true);
    expect(auth.isAuthenticated()).toBe(true);
    expect(auth.can('manage_eggs')).toBe(true);
    expect(auth.offlineSession()).toBe(true);
    expect(auth.hasRefreshToken()).toBe(true);
  });

  it('sans profil gardé, renvoie à la connexion mais garde le jeton', () => {
    localStorage.setItem('avika.refresh', 'r1');
    let result: boolean | undefined;
    auth.restoreSession().subscribe((value) => (result = value));
    http.expectOne('/api/v1/auth/refresh/').error(new ProgressEvent('error'));
    expect(result).toBe(false);
    expect(auth.hasRefreshToken()).toBe(true);
  });

  it('déconnecte sur un vrai refus du serveur et efface le profil gardé', () => {
    localStorage.setItem('avika.refresh', 'r1');
    localStorage.setItem('avika.profile', JSON.stringify(ME));
    let result: boolean | undefined;
    auth.restoreSession().subscribe((value) => (result = value));
    http
      .expectOne('/api/v1/auth/refresh/')
      .flush({ detail: 'refusé' }, { status: 401, statusText: 'Unauthorized' });
    expect(result).toBe(false);
    expect(auth.hasRefreshToken()).toBe(false);
    expect(localStorage.getItem('avika.profile')).toBeNull();
  });

  it('mémorise le profil après une ouverture de session réussie', () => {
    localStorage.setItem('avika.refresh', 'r1');
    auth.restoreSession().subscribe();
    http.expectOne('/api/v1/auth/refresh/').flush({ access: 'a1' });
    http.expectOne('/api/v1/auth/me/').flush(ME);
    expect(localStorage.getItem('avika.profile')).toContain('Awa Diallo');
    expect(auth.offlineSession()).toBe(false);
  });

  it('efface le profil gardé à la déconnexion', () => {
    localStorage.setItem('avika.profile', JSON.stringify(ME));
    auth.clearSession();
    expect(localStorage.getItem('avika.profile')).toBeNull();
  });
});
