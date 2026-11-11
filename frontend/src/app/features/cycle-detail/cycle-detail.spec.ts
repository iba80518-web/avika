import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';

import { AuthService } from '../../core/auth.service';
import { CycleDetail } from './cycle-detail';

const CYCLE = {
  id: 2, coop: 2, name: 'Bande B', type: 'broiler', start_date: '2026-10-29', end_date: null,
  initial_count: 500, supplier_name: '', unit_price: 9000, currency: 'GNF', target: '',
  planned_sale_date: null, status: 'active', current_count: 430, created_at: '2026-11-10T00:00:00Z',
};
const SUMMARY = {
  initial_count: 500, entries: 0, transfers_in: 0, mortality: 70, sold: 0, transfers_out: 0,
  corrections: 0, current_count: 430, mortality_rate: 14,
};
const EVENT = {
  id: 13, uuid: 'u', event_type: 'mortality', quantity: 20, event_date: '2026-11-11',
  cause: 'Chaleur', note: '', created_by: 3, created_at: '2026-11-11T11:00:00Z',
};
const page = (results: unknown[]) => ({ count: results.length, next: null, previous: null, results });

describe('CycleDetail', () => {
  let fixture: ComponentFixture<CycleDetail>;
  let root: HTMLElement;
  let http: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [CycleDetail],
      providers: [
        provideRouter([]),
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: ActivatedRoute, useValue: { snapshot: { paramMap: convertToParamMap({ id: '2' }) } } },
        { provide: AuthService, useValue: { can: () => true } },
      ],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(CycleDetail);
    root = fixture.nativeElement as HTMLElement;
    fixture.detectChanges();
    http.expectOne('/api/v1/cycles/2/').flush(CYCLE);
    http.expectOne('/api/v1/cycles/2/summary/').flush(SUMMARY);
    http.expectOne('/api/v1/cycles/2/events/').flush(page([EVENT]));
    http.expectOne('/api/v1/coops/').flush(page([{ id: 2, farm: 1, name: 'Poulailler B', capacity: 800, type: 'broiler', location: '', status: 'active', description: '' }]));
    await fixture.whenStable();
    fixture.detectChanges();
  });

  afterEach(() => http.verify());

  function fill(value: string): void {
    const input = root.querySelector<HTMLInputElement>('#quantity') as HTMLInputElement;
    input.value = value;
    input.dispatchEvent(new Event('input'));
  }

  function submit(): void {
    (root.querySelector('form') as HTMLFormElement).dispatchEvent(new Event('submit'));
  }

  it('affiche les chiffres, le poulailler et l’historique', () => {
    const text = root.textContent ?? '';
    expect(text).toContain('Bande B');
    expect(text).toContain('Poulailler B');
    expect(text).toContain('14');
    expect(text).toContain('−20');
  });

  it('envoie la mortalité avec un identifiant unique puis relit les chiffres', async () => {
    fill('3');
    (root.querySelectorAll<HTMLButtonElement>('.chip')[0]).click();
    submit();
    const request = http.expectOne('/api/v1/cycles/2/events/');
    expect(request.request.method).toBe('POST');
    expect(request.request.body.quantity).toBe(3);
    expect(request.request.body.cause).toBe('Chaleur');
    expect(request.request.body.uuid).toBeTruthy();
    request.flush({ ...EVENT, id: 14, quantity: 3 }, { status: 201, statusText: 'Created' });
    http.expectOne('/api/v1/cycles/2/summary/').flush({ ...SUMMARY, current_count: 427 });
    http.expectOne('/api/v1/cycles/2/events/').flush(page([EVENT]));
    await fixture.whenStable();
    fixture.detectChanges();
    expect(root.textContent).toContain('3 mortalité(s) enregistrée(s).');
  });

  it('garde le même identifiant quand on réessaie après une coupure', async () => {
    fill('2');
    submit();
    const first = http.expectOne('/api/v1/cycles/2/events/');
    const uuid = first.request.body.uuid;
    first.error(new ProgressEvent('error'));
    await fixture.whenStable();
    fixture.detectChanges();
    expect(root.querySelector('[role="alert"]')?.textContent).toContain('Pas de connexion');
    submit();
    const second = http.expectOne('/api/v1/cycles/2/events/');
    expect(second.request.body.uuid).toBe(uuid);
    second.error(new ProgressEvent('error'));
  });

  function click(label: string): void {
    const button = Array.from(root.querySelectorAll<HTMLButtonElement>('.actions button')).find((item) =>
      item.textContent?.includes(label),
    );
    (button as HTMLButtonElement).click();
    fixture.detectChanges();
  }

  it('termine la bande après confirmation', async () => {
    click('Terminer la bande');
    click('Confirmer');
    const request = http.expectOne('/api/v1/cycles/2/complete/');
    expect(request.request.method).toBe('POST');
    request.flush({ ...CYCLE, status: 'completed' });
    http.expectOne('/api/v1/cycles/2/summary/').flush(SUMMARY);
    http.expectOne('/api/v1/cycles/2/events/').flush(page([EVENT]));
    await fixture.whenStable();
    fixture.detectChanges();
    expect(root.textContent).toContain('Terminée');
    expect(root.querySelector('.actions')).toBeNull();
  });

  it('affiche le refus du serveur sans changer la bande', async () => {
    click('Annuler la bande');
    click('Confirmer');
    http
      .expectOne('/api/v1/cycles/2/cancel/')
      .flush({ detail: 'Action impossible.' }, { status: 400, statusText: 'Bad Request' });
    await fixture.whenStable();
    fixture.detectChanges();
    expect(root.textContent).toContain('Action impossible.');
    expect(root.textContent).toContain('En cours');
  });
});
