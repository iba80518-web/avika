import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';

import { localToday } from '../../core/dates';
import { HealthForm } from './health-form';

const CYCLE = {
  id: 2, coop: 2, name: 'Bande B', type: 'broiler', start_date: '2026-10-29', end_date: null,
  initial_count: 500, supplier_name: '', unit_price: 9000, currency: 'GNF', target: '',
  planned_sale_date: null, status: 'active', current_count: 430, created_at: '2026-11-10T00:00:00Z',
};
const TEMPLATE = { id: 5, name: 'Poulet de chair 35 jours', description: '', is_active: true, items: [{}, {}], created_at: '2026-11-10T00:00:00Z' };
const page = (results: unknown[]) => ({ count: results.length, next: null, previous: null, results });

describe('HealthForm', () => {
  let fixture: ComponentFixture<HealthForm>;
  let root: HTMLElement;
  let http: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [HealthForm],
      providers: [provideRouter([{ path: 'sante', children: [] }]), provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(HealthForm);
    root = fixture.nativeElement as HTMLElement;
    fixture.detectChanges();
    http.expectOne('/api/v1/cycles/').flush(page([CYCLE]));
    http.expectOne('/api/v1/products/').flush(page([]));
    http.expectOne('/api/v1/health-templates/').flush(page([TEMPLATE]));
    await fixture.whenStable();
    fixture.detectChanges();
  });

  afterEach(() => http.verify());

  function fill(id: string, value: string): void {
    const input = root.querySelector<HTMLInputElement>('#' + id) as HTMLInputElement;
    input.value = value;
    input.dispatchEvent(new Event('input'));
    fixture.detectChanges();
  }

  function choose(id: string, value: string): void {
    const select = root.querySelector<HTMLSelectElement>('#' + id) as HTMLSelectElement;
    select.value = value;
    select.dispatchEvent(new Event('change'));
    fixture.detectChanges();
  }

  function tab(label: string): void {
    const button = Array.from(root.querySelectorAll<HTMLButtonElement>('.seg button')).find((item) =>
      item.textContent?.includes(label),
    );
    (button as HTMLButtonElement).click();
    fixture.detectChanges();
  }

  const submit = (): void => {
    (root.querySelector('form') as HTMLFormElement).dispatchEvent(new Event('submit'));
  };

  it('exige la bande et le nom, sans contacter le serveur', async () => {
    submit();
    await fixture.whenStable();
    fixture.detectChanges();
    http.expectNone('/api/v1/health-tasks/');
    expect(root.querySelector('[role="alert"]')?.textContent).toContain('bande');
  });

  it('enregistre une tâche puis revient à la liste', async () => {
    choose('cycle', '2');
    fill('name', 'Rappel Gumboro');
    submit();
    const request = http.expectOne('/api/v1/health-tasks/');
    expect(request.request.method).toBe('POST');
    expect(request.request.body.cycle).toBe(2);
    expect(request.request.body.name).toBe('Rappel Gumboro');
    expect(request.request.body.kind).toBe('vaccine');
    expect(request.request.body.due_date).toBe(localToday());
    expect(request.request.body.product).toBeUndefined();
    expect(request.request.body.uuid).toBeTruthy();
    request.flush({ id: 9 }, { status: 201, statusText: 'Created' });
    await fixture.whenStable();
    expect(TestBed.inject(Router).url).toBe('/sante');
  });

  it('planifie un calendrier type et signale quand il est déjà planifié', async () => {
    tab('Calendrier type');
    choose('cycle', '2');
    choose('template', '5');
    submit();
    const request = http.expectOne('/api/v1/health-tasks/schedule/');
    expect(request.request.body).toEqual({ cycle: 2, template: 5 });
    request.flush([], { status: 200, statusText: 'OK' });
    await fixture.whenStable();
    fixture.detectChanges();
    expect(root.querySelector('[role="status"]')?.textContent).toContain('déjà planifié');
  });
});
