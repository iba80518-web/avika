import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ActivatedRoute, Router, convertToParamMap, provideRouter } from '@angular/router';

import { localToday } from '../../core/dates';
import { ExpenseForm } from './expense-form';

const CYCLE = {
  id: 1, coop: 1, name: 'Bande A', type: 'broiler', start_date: '2026-10-01', end_date: null,
  initial_count: 1000, supplier_name: '', unit_price: 9000, currency: 'GNF', target: '',
  planned_sale_date: null, status: 'active', current_count: 700, created_at: '2026-11-10T00:00:00Z',
};
const EXPENSE = {
  id: 4, uuid: 'e4', amount: 50000, expense_date: '2026-11-05', category: 'labor',
  description: 'Salaire gardien', supplier: null, cycle: 1, created_by: 3, created_at: '2026-11-10T00:00:00Z',
};
const page = (results: unknown[]) => ({ count: results.length, next: null, previous: null, results });

describe('ExpenseForm', () => {
  let fixture: ComponentFixture<ExpenseForm>;
  let root: HTMLElement;
  let http: HttpTestingController;

  async function setup(id: string | null): Promise<void> {
    await TestBed.configureTestingModule({
      imports: [ExpenseForm],
      providers: [
        provideRouter([{ path: 'depenses', children: [] }]),
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: ActivatedRoute, useValue: { snapshot: { paramMap: convertToParamMap(id ? { id } : {}) } } },
      ],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(ExpenseForm);
    root = fixture.nativeElement as HTMLElement;
    fixture.detectChanges();
    if (id) http.expectOne('/api/v1/expenses/' + id + '/').flush(EXPENSE);
    http.expectOne('/api/v1/cycles/').flush(page([CYCLE]));
    await fixture.whenStable();
    fixture.detectChanges();
  }

  afterEach(() => http.verify());

  function fill(id: string, value: string): void {
    const input = root.querySelector<HTMLInputElement>('#' + id) as HTMLInputElement;
    input.value = value;
    input.dispatchEvent(new Event('input'));
    fixture.detectChanges();
  }

  function chip(label: string): void {
    const button = Array.from(root.querySelectorAll<HTMLButtonElement>('.chips button')).find((item) =>
      item.textContent?.includes(label),
    );
    (button as HTMLButtonElement).click();
    fixture.detectChanges();
  }

  const submit = (): void => {
    (root.querySelector('form') as HTMLFormElement).dispatchEvent(new Event('submit'));
  };

  it('exige une catégorie, sans contacter le serveur', async () => {
    await setup(null);
    fill('amount', '15000');
    submit();
    await fixture.whenStable();
    fixture.detectChanges();
    http.expectNone('/api/v1/expenses/');
    expect(root.querySelector('[role="alert"]')?.textContent).toContain('catégorie');
  });

  it('enregistre une nouvelle dépense puis revient à la liste', async () => {
    await setup(null);
    chip('Transport');
    fill('amount', '15 000');
    submit();
    const request = http.expectOne('/api/v1/expenses/');
    expect(request.request.method).toBe('POST');
    expect(request.request.body.amount).toBe(15000);
    expect(request.request.body.category).toBe('transport');
    expect(request.request.body.expense_date).toBe(localToday());
    expect(request.request.body.cycle).toBeUndefined();
    expect(request.request.body.uuid).toBeTruthy();
    request.flush({ ...EXPENSE, id: 9 }, { status: 201, statusText: 'Created' });
    await fixture.whenStable();
    expect(TestBed.inject(Router).url).toBe('/depenses');
  });

  it('charge une dépense existante et envoie la correction', async () => {
    await setup('4');
    expect((root.querySelector('#amount') as HTMLInputElement).value).toBe('50000');
    expect(root.querySelector('h1')?.textContent).toContain('Modifier');
    fill('amount', '60000');
    submit();
    const request = http.expectOne('/api/v1/expenses/4/');
    expect(request.request.method).toBe('PATCH');
    expect(request.request.body.amount).toBe(60000);
    expect(request.request.body.category).toBe('labor');
    expect(request.request.body.cycle).toBe(1);
    request.flush({ ...EXPENSE, amount: 60000 });
    await fixture.whenStable();
    expect(TestBed.inject(Router).url).toBe('/depenses');
  });
});
