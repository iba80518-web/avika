import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { formatCompact, formatMoney } from '../../core/money';
import { Sales } from './sales';

const sale = (id: number, customer: number | null, name: string | null, total: number, paid: number, status: string) => ({
  id, uuid: 'u' + id, customer, customer_name: name, cycle: 1, sale_date: '2026-11-07', sale_type: 'count',
  quantity: 100, weight_kg: null, unit_price: total / 100, total_amount: total, paid, balance: total - paid,
  status, note: '', created_by: 3, created_at: '2026-11-10T00:00:00Z',
});
const CYCLE = {
  id: 1, coop: 1, name: 'Bande A', type: 'broiler', start_date: '2026-10-01', end_date: null,
  initial_count: 1000, supplier_name: '', unit_price: 9000, currency: 'GNF', target: '',
  planned_sale_date: null, status: 'active', current_count: 700, created_at: '2026-11-10T00:00:00Z',
};
const page = (results: unknown[]) => ({ count: results.length, next: null, previous: null, results });

describe('Sales', () => {
  let fixture: ComponentFixture<Sales>;
  let root: HTMLElement;
  let http: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [Sales],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(Sales);
    root = fixture.nativeElement as HTMLElement;
    fixture.detectChanges();
    http.expectOne('/api/v1/sales/').flush(
      page([
        sale(1, 1, 'Boucherie Diallo', 4000000, 2500000, 'active'),
        sale(2, null, null, 800000, 800000, 'active'),
        sale(3, 1, 'Boucherie Diallo', 500000, 0, 'cancelled'),
      ]),
    );
    http.expectOne('/api/v1/sales/receivables/').flush([
      { customer: 1, customer_name: 'Boucherie Diallo', total_due: 1500000, sales_count: 1 },
    ]);
    http.expectOne('/api/v1/cycles/').flush(page([CYCLE]));
    await fixture.whenStable();
    fixture.detectChanges();
  });

  afterEach(() => http.verify());

  it('affiche chaque vente avec son état : payée, à solder, annulée', () => {
    const text = root.textContent ?? '';
    expect(text).toContain('Boucherie Diallo');
    expect(text).toContain('Client de passage');
    expect(text).toContain('Bande A');
    expect(text).toContain('Payée');
    expect(text).toContain('Annulée');
    expect(text).toContain('Reste ' + formatMoney(1500000));
  });

  it('résume les ventes valides et ce qu’il reste à recevoir', () => {
    const values = Array.from(root.querySelectorAll('.kpi__value')).map((item) => item.textContent ?? '');
    expect(values[0]).toContain(formatCompact(4800000));
    expect(values[1]).toContain(formatCompact(3300000));
    expect(values[2]).toContain(formatCompact(1500000));
    expect(root.textContent).toContain('Qui doit encore de l’argent');
  });
});
