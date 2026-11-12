import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';

import { formatMoney } from '../../core/money';
import { SaleDetail } from './sale-detail';

const SALE = {
  id: 1, uuid: 'u1', customer: 5, customer_name: 'Boucherie Diallo', cycle: 2, sale_date: '2026-11-07',
  sale_type: 'count', quantity: 100, weight_kg: null, unit_price: 40000, total_amount: 4000000,
  paid: 2500000, balance: 1500000, status: 'active', note: '', created_by: 3, created_at: '2026-11-10T00:00:00Z',
};
const PAYMENT = {
  id: 4, uuid: 'p', sale: 1, amount: 2500000, payment_date: '2026-11-07', method: 'cash',
  created_by: 3, created_at: '2026-11-10T00:00:00Z',
};
const CYCLE = {
  id: 2, coop: 2, name: 'Bande B', type: 'broiler', start_date: '2026-10-29', end_date: null,
  initial_count: 500, supplier_name: '', unit_price: 9000, currency: 'GNF', target: '',
  planned_sale_date: null, status: 'active', current_count: 430, created_at: '2026-11-10T00:00:00Z',
};
const page = (results: unknown[]) => ({ count: results.length, next: null, previous: null, results });

describe('SaleDetail', () => {
  let fixture: ComponentFixture<SaleDetail>;
  let root: HTMLElement;
  let http: HttpTestingController;

  async function open(payments: unknown[]): Promise<void> {
    fixture.detectChanges();
    http.expectOne('/api/v1/sales/1/').flush(SALE);
    http.expectOne('/api/v1/sales/1/payments/').flush(payments);
    http.expectOne('/api/v1/cycles/').flush(page([CYCLE]));
    await fixture.whenStable();
    fixture.detectChanges();
  }

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SaleDetail],
      providers: [
        provideRouter([]),
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: ActivatedRoute, useValue: { snapshot: { paramMap: convertToParamMap({ id: '1' }) } } },
      ],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(SaleDetail);
    root = fixture.nativeElement as HTMLElement;
  });

  afterEach(() => http.verify());

  function fill(id: string, value: string): void {
    const input = root.querySelector<HTMLInputElement>('#' + id) as HTMLInputElement;
    input.value = value;
    input.dispatchEvent(new Event('input'));
    fixture.detectChanges();
  }

  const submit = (): void => {
    (root.querySelector('form') as HTMLFormElement).dispatchEvent(new Event('submit'));
  };

  it('affiche les montants, la bande et les paiements reçus', async () => {
    await open([PAYMENT]);
    const text = root.textContent ?? '';
    expect(text).toContain('Boucherie Diallo');
    expect(text).toContain('Bande B');
    expect(text).toContain(formatMoney(1500000));
    expect(text).toContain('Espèces');
  });

  it('n’offre pas l’annulation quand la vente a déjà reçu un paiement', async () => {
    await open([PAYMENT]);
    expect(root.textContent).not.toContain('Annuler la vente');
    expect(root.textContent).toContain('ne peut plus être annulée');
  });

  it('refuse un paiement supérieur au reste à payer, sans contacter le serveur', async () => {
    await open([PAYMENT]);
    fill('amount', '2000000');
    submit();
    await fixture.whenStable();
    fixture.detectChanges();
    http.expectNone('/api/v1/sales/1/payments/');
    expect(root.querySelector('[role="alert"]')?.textContent).toContain('dépasse le reste à payer');
  });

  it('enregistre un paiement puis relit la vente', async () => {
    await open([PAYMENT]);
    fill('amount', '1500000');
    submit();
    const request = http.expectOne('/api/v1/sales/1/payments/');
    expect(request.request.method).toBe('POST');
    expect(request.request.body.amount).toBe(1500000);
    expect(request.request.body.method).toBe('cash');
    expect(request.request.body.uuid).toBeTruthy();
    request.flush({ ...PAYMENT, id: 9, amount: 1500000 }, { status: 201, statusText: 'Created' });
    http.expectOne('/api/v1/sales/1/').flush({ ...SALE, paid: 4000000, balance: 0 });
    http.expectOne('/api/v1/sales/1/payments/').flush([PAYMENT]);
    await fixture.whenStable();
    fixture.detectChanges();
    expect(root.textContent).toContain('Paiement de ' + formatMoney(1500000) + ' enregistré.');
    expect(root.textContent).toContain('Payée');
  });
});
