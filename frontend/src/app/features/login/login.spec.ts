import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { Login } from './login';

describe('Login', () => {
  let fixture: ComponentFixture<Login>;
  let root: HTMLElement;
  let http: HttpTestingController;

  beforeEach(async () => {
    localStorage.clear();
    await TestBed.configureTestingModule({
      imports: [Login],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(Login);
    fixture.detectChanges();
    root = fixture.nativeElement as HTMLElement;
  });

  afterEach(() => http.verify());

  function fill(id: string, value: string): void {
    const input = root.querySelector<HTMLInputElement>('#' + id) as HTMLInputElement;
    input.value = value;
    input.dispatchEvent(new Event('input'));
  }

  function submit(): void {
    (root.querySelector('form') as HTMLFormElement).dispatchEvent(new Event('submit'));
  }

  it('ne contacte pas le serveur si le formulaire est vide', async () => {
    submit();
    await fixture.whenStable();
    fixture.detectChanges();
    http.expectNone('/api/v1/auth/login/');
    expect(root.querySelector('[role="alert"]')).not.toBeNull();
  });

  it('affiche un message clair après un mot de passe refusé', async () => {
    fill('identifier', 'dev@avika.test');
    fill('password', 'mauvais');
    submit();
    http
      .expectOne('/api/v1/auth/login/')
      .flush({ detail: 'x' }, { status: 401, statusText: 'Unauthorized' });
    await fixture.whenStable();
    fixture.detectChanges();
    expect(root.textContent).toContain('incorrect');
    expect((root.querySelector('button[type="submit"]') as HTMLButtonElement).disabled).toBe(false);
  });

  it('bloque le bouton pendant la connexion', async () => {
    fill('identifier', 'dev@avika.test');
    fill('password', 'secret');
    submit();
    fixture.detectChanges();
    expect((root.querySelector('button[type="submit"]') as HTMLButtonElement).disabled).toBe(true);
    http.expectOne('/api/v1/auth/login/').flush({ detail: 'x' }, { status: 401, statusText: 'x' });
    await fixture.whenStable();
  });
});
