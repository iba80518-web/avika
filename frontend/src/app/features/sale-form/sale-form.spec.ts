import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';

import { formatMoney } from '../../core/money';
import { SaleForm } from './sale-form';

const CYCLE = {
  id: 2, coop: 2, name: 'Bande B', type: 'broiler', start_date: '2026-10-29', end_date: null,
  initial_count: 500, supplier_name: '', unit_price: 9000, currency: 'GNF', target: '',
  planned_sale_date: null, status: 'active', current_count: 430, created_at: '2026-11-10T00:00:00Z',
};
const CUSTOMER = {
  id: 5, name: 'Boucherie Diallo', phone: '', address: '', customer_type: 'butcher', is_active: true,
  created_at: '2026-11-10T00:00:00Z',
};
const page = (results: unknown[]) => ({ count: results.length, next: null, previous: null, results });

describe('SaleForm', () => {
  let fixture: ComponentFixture<SaleForm>;
  let root: HTMLElement;
  let http: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SaleForm],
      providers: [
        provideRouter([{ path: 'ventes/:id', children: [] }]),
        provideHttpClient(),
        provideHttpClientTesting(),
      ],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(SaleForm);
    root = fixture.nativeElement as HTMLElement;
    fixture.detectChanges();
    http.expectOne('/api/v1/cycles/').flush(page([CYCLE]));
    http.expectOne('/api/v1/customers/').flush(page([CUSTOMER]));
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

  const submit = (): void => {
    (root.querySelector('form') as HTMLFormElement).dispatchEvent(new Event('submit'));
  };

  it('calcule le total en direct', () => {
    fill('qty', '100');
    fill('price', '25000');
    expect(root.querySelector('.total')?.textContent).toContain(formatMoney(2500000));
  });

  it('exige un client quand la vente n’est pas payée en totalité, sans contacter le serveur', async () => {
    choose('cycle', '2');
    fill('qty', '100');
    fill('price', '25000');
    fill('paid', '0');
    submit();
    await fixture.whenStable();
    fixture.detectChanges();
    http.expectNone('/api/v1/sales/');
    expect(root.querySelector('[role="alert"]')?.textContent).toContain('client');
  });

  it('refuse de vendre plus de poulets que l’effectif de la bande', async () => {
    choose('cycle', '2');
    fill('qty', '500');
    fill('price', '25000');
    submit();
    await fixture.whenStable();
    fixture.detectChanges();
    http.expectNone('/api/v1/sales/');
    expect(root.querySelector('[role="alert"]')?.textContent).toContain('430');
  });

  it('envoie la vente payée en totalité par défaut, puis ouvre sa fiche', async () => {
    choose('cycle', '2');
    fill('qty', '100');
    fill('price', '25000');
    submit();
    const request = http.expectOne('/api/v1/sales/');
    expect(request.request.method).toBe('POST');
    expect(request.request.body.cycle).toBe(2);
    expect(request.request.body.sale_type).toBe('count');
    expect(request.request.body.quantity).toBe(100);
    expect(request.request.body.unit_price).toBe(25000);
    expect(request.request.body.paid_amount).toBe(2500000);
    expect(request.request.body.customer).toBeUndefined();
    expect(request.request.body.uuid).toBeTruthy();
    request.flush({ id: 7 }, { status: 201, statusText: 'Created' });
    await fixture.whenStable();
    expect(TestBed.inject(Router).url).toBe('/ventes/7');
  });
});
