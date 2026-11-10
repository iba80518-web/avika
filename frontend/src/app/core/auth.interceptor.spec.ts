import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { authInterceptor } from './auth.interceptor';
import { AuthService } from './auth.service';

const ME = {
  user: { id: 3, full_name: 'Dev Local', email: 'dev@avika.test', phone: null },
  memberships: [
    {
      organization: { id: 7, name: 'Ferme Dev', reference_currency: 'GNF' },
      role: 'owner',
      permissions: ['view_dashboard'],
    },
  ],
};

describe('authInterceptor', () => {
  let auth: AuthService;
  let client: HttpClient;
  let http: HttpTestingController;

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({
      providers: [
        provideRouter([{ path: 'connexion', children: [] }]),
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    auth = TestBed.inject(AuthService);
    client = TestBed.inject(HttpClient);
    http = TestBed.inject(HttpTestingController);
    auth.login('dev@avika.test', 'secret').subscribe();
    http.expectOne('/api/v1/auth/login/').flush({ access: 'A1', refresh: 'R1' });
    http.expectOne('/api/v1/auth/me/').flush(ME);
  });

  afterEach(() => http.verify());

  it('ajoute le jeton et l’exploitation active aux appels vers l’API', () => {
    client.get('/api/v1/farms/').subscribe();
    const request = http.expectOne('/api/v1/farms/');
    expect(request.request.headers.get('Authorization')).toBe('Bearer A1');
    expect(request.request.headers.get('X-Organization')).toBe('7');
    request.flush([]);
  });

  it('n’ajoute rien aux adresses hors de l’API', () => {
    client.get('/autre/chose').subscribe();
    const request = http.expectOne('/autre/chose');
    expect(request.request.headers.has('Authorization')).toBe(false);
    request.flush({});
  });

  it('renouvelle le jeton après un 401 puis rejoue la requête', () => {
    let body: unknown = null;
    client.get('/api/v1/farms/').subscribe((value) => (body = value));
    http
      .expectOne('/api/v1/farms/')
      .flush({ detail: 'expiré' }, { status: 401, statusText: 'Unauthorized' });
    http.expectOne('/api/v1/auth/refresh/').flush({ access: 'A2', refresh: 'R2' });
    const retry = http.expectOne('/api/v1/farms/');
    expect(retry.request.headers.get('Authorization')).toBe('Bearer A2');
    retry.flush([{ id: 1 }]);
    expect(body).toEqual([{ id: 1 }]);
  });

  it('ferme la session si le renouvellement échoue', () => {
    let failed = false;
    client.get('/api/v1/farms/').subscribe({ error: () => (failed = true) });
    http
      .expectOne('/api/v1/farms/')
      .flush({ detail: 'expiré' }, { status: 401, statusText: 'Unauthorized' });
    http
      .expectOne('/api/v1/auth/refresh/')
      .flush({ detail: 'périmé' }, { status: 401, statusText: 'Unauthorized' });
    expect(failed).toBe(true);
    expect(auth.isAuthenticated()).toBe(false);
  });
});
